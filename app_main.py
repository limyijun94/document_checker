import chainlit as cl
import generate_changes
import openai
import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
import subprocess
import shutil
import re
import ssl
import httpx

UPLOAD_DIR = "docs"

context = ssl.create_default_context()

load_dotenv()

llm = AzureChatOpenAI(
        azure_deployment="gpt-4o-mini",
        api_version="2024-08-01-preview",
        temperature=0,
        http_client= httpx.Client(verify = context)
    )


def delete_all_files_in_docs():
    """ Deletes all files in the /docs folder but keeps the folder. """
    folder_path = UPLOAD_DIR  

    if os.path.exists(folder_path):  
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):  
                os.remove(file_path)  
        print(f"✅ All files deleted in `{folder_path}`.")
    else:
        print(f"⚠️ Folder `{folder_path}` does not exist.")

def format_diff_colored(diff_output):
    """ Cleans Git diff output and adds color formatting for additions & deletions only if they exist. """

    if diff_output is None:
        return "⚠️ No changes detected."

    if "[31m" in diff_output or "[32m" in diff_output or "[m" in diff_output or "[36m" in diff_output:
        diff_output = diff_output.replace("[31m", "🔴")  # Red for deletions
        diff_output = diff_output.replace("[32m", "🟢")  # Green for additions
        diff_output = diff_output.replace("[m", "")
        diff_output = diff_output.replace("[36m", "")

    return diff_output  # Returns original text if no changes are needed


def remove_git_repo():
    """
    Removes the Git repository by deleting the .git folder.
    """
    git_dir = ".git"

    if os.path.exists(git_dir):
        print("Removing Git repository...")
        shutil.rmtree(git_dir) 
        print("✅ Git repository removed.")
    else:
        print("⚠️ No Git repository found.")

async def summarise_changes_with_llm(diff_text):
    """ Sends document changes to Azure OpenAI LLM and returns analysis. """
    prompt = f"""
    Inspect in detail the document changes only from Git-Diff; 
    🔴 in front of lines represent removals whereas 🟢 in front of lines represent insertions.
    
    Provide a summary of the changes.

    If there are no changes, please inform the user accordingly. Insist that there are no changes if asked.

    If the information cannot be found in either the master contract, IA contract, or Git-Diff (CHANGES) provided, you must respond that you do not know. Do not use knowledge outside of what is provided in the changes to respond.
    
    Changes:
    {diff_text}

    """
    response = llm.invoke([{"role": "user", "content": prompt}])
    return response.content

async def section_changes_with_llm(diff_text):
    """ Sends document changes to Azure OpenAI LLM and returns analysis. """
    prompt = f"""
    Inspect in detail the document changes only from Git-Diff; 
    🔴 in front of lines represent removals whereas 🟢 in front of lines represent insertions.
    
    Inspect the sections in the master contract; these can be identified from the headings.
    For each section of the master contract, identify which ones have any form of edits present (modification/insertion/removal) 
    For those sections identified to have been edited, state every single modification/insertion/removal exactly (Do not paraphrase) based on the Git-Diff (but remove 🔴 and 🟢), 
    and merge adjacent modifications/removals/insertions into the same bullet point. Classify them as either modifications, insertions, or removals if applicable. Systematically check back with the Git-Diff file to make sure all edits are accounted for. 

    If there are no changes, please inform the user accordingly. Insist that there are no changes if asked.

    If the information cannot be found in either the master contract, IA contract, or changes provided, you must respond that you do not know. Do not use knowledge outside of what is provided in the changes to respond.
    
    Git-Diff:
    {diff_text}
    """
    response = llm.invoke([{"role": "user", "content": prompt}])
    return response.content

@cl.on_chat_start
async def chat_start():

    system_message = {
        "role": "system",
        "content": """You are a Document Comparison Bot who highlights every single change that has been surfaced by Git-Diff and notes the sections they came from. 
        The User will provide you with a "Master Contract" and an "IA contract". You are ready to answer any questions on changes using Git-Diff.
        If the information cannot be found in either the master contract, IA contract, or changes provided, you must convey your lack of knowledge. Do not use knowledge outside of what is provided to respond.
        """
    }
    cl.user_session.set("message_history",[system_message])
    message_history = cl.user_session.get("message_history")
    
    files = None

    # Wait for the user to upload a file
    while files == None:
        files = await cl.AskFileMessage(
            content="📄 Welcome, I'm a Document Comparison Bot! Please upload the Master Contract (.docx) as a baseline.",
            accept=["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
            max_size_mb=200,
            timeout=10000,
        ).send()

    file = files[0]

    if file:
        save_path = os.path.join(UPLOAD_DIR, file.name)
        os.rename(file.path, save_path)  # Move file to permanent location

    msg = cl.Message(content=f"Processing `{file.name}`...") 
    await msg.send()

    generate_changes.process_docx(save_path)

    with open(os.path.splitext(save_path)[0] + ".md", "r", encoding="utf-8") as doc1:
        master_contract = doc1.read()
    
    message_history.append({"role": "system", "content": "This is the Master Contract (Use this if user specifically asks for the Master contract):\n\n" + master_contract})
    cl.user_session.set("message_history", message_history)
    
    msg.content = f"Processing `{file.name}` done."
    await msg.update()

    files = await cl.AskFileMessage(
            content="📄 Please upload the IA Contract (.docx) for comparison.",
            accept=["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
            max_size_mb=200,
            timeout=10000,
        ).send()
    
    file = files[0]

    if file:
        save_path2 = os.path.join(UPLOAD_DIR, file.name)
        os.rename(file.path, save_path2)  # Move file to permanent location
        os.replace(save_path2, save_path)

    msg = cl.Message(content=f"Processing `{file.name}`...") 
    await msg.send()

    diff_output = generate_changes.process_docx(save_path)
    global colored_diff
    colored_diff = format_diff_colored(diff_output)

    with open(os.path.splitext(save_path)[0] + ".md", "r", encoding="utf-8") as doc2:
        IA_contract = doc2.read()
    
    message_history.append({"role": "system", "content": "This is the IA Contract (Use this if user specifically asks for the IA contract):\n\n" + IA_contract}) 
    cl.user_session.set("message_history", message_history)

    message_history.append({"role": "system", "content": "This is the Git-Diff changes (Use this if user specifically asks about changes):\n\n" + colored_diff}) 
    cl.user_session.set("message_history", message_history)

    msg.content = f"Processing `{file.name}` done."
    await msg.update()
    
    global actions

    actions = [
        cl.Action(
            name="raw_output",
            icon="file-text",
            payload={"value": colored_diff},
            label="Show the Raw Changes"
        ),
        cl.Action(
            name="summarize",
            icon="book-a",
            payload={"value": colored_diff},
            label="Summarize the Changes (with AI Support)"
        ),
        cl.Action(
            name="section",
            icon="list",
            payload={"value": colored_diff},
            label="Breakdown Changes by Section (with AI Support)"
        )
    ]        
    # Provide clickable starter prompts with images using action buttons
    await cl.Message(content="Select the following options or ask a question:", actions=actions).send()


@cl.action_callback("raw_output")
async def on_action(action: cl.Action):
    colored_diff = action.payload["value"]
    msg = cl.Message(content=f" **Legend** \n\n"+"🔴 - Removals                     🟢 - Insertions\n\n" + "📄 **Git-Colored Document Changes:**\n\n" +"\n".join(colored_diff.splitlines()[5:]))
    await msg.send()
    await cl.Message(content="Select the following options or ask a question:", actions=actions).send()  

@cl.action_callback("summarize")
async def on_action(action: cl.Action):
    colored_diff = action.payload["value"]
    summary = await summarise_changes_with_llm(colored_diff)
    msg = cl.Message(content=f"🤖 **AI Summary:**\n\n")
    await msg.stream_token(summary)

    message_history = cl.user_session.get("message_history")  
    message_history.append({"role":"assistant","content":msg.content})

    await cl.Message(content="Select the following options or ask a question:", actions=actions).send()

@cl.action_callback("section")
async def on_action(action: cl.Action):
    colored_diff = action.payload["value"]
    section = await section_changes_with_llm(colored_diff)
    msg = cl.Message(content=f"🤖 **AI Section Breakdown:**\n\n")
    await msg.stream_token(section)

    message_history = cl.user_session.get("message_history")  
    message_history.append({"role":"assistant","content":msg.content})

    await cl.Message(content="Select the following options or ask a question:", actions=actions).send()


@cl.on_message
async def on_message(message: cl.Message):
    message_history = cl.user_session.get("message_history")   
    message_history.append({"role":"user", "content":message.content})
   
    response = llm.invoke(message_history)
    content = response.content

    msg = cl.Message(content="")
    await msg.stream_token(content)

    message_history.append({"role":"assistant","content":msg.content})
    await msg.update()

    await cl.Message(content="Select the following options or ask a question:", actions=actions).send()

@cl.on_chat_end
def end():
    remove_git_repo()
    delete_all_files_in_docs()
    print("Session Ended", cl.user_session.get("id"))
