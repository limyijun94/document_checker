import os
import subprocess
import git
import sys
import difflib

def convert_docx_to_md(docx_file):
    """
    Converts a .docx file to Markdown (.md) using pandoc.
    Returns the generated markdown filename.
    """
    md_file = os.path.splitext(docx_file)[0] + ".md"
    try:
        subprocess.run(["pandoc", docx_file, "-t", "markdown", "-o", md_file], check=True)
        print(f"Converted {docx_file} to {md_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error converting {docx_file}: {e}")
        sys.exit(1)
    return md_file

def initialize_git():
    """
    Initializes a Git repository if it does not exist.
    """
    if not os.path.exists(".git"):
        print("Initializing Git repository...")
        subprocess.run(["git", "init"], check=True)

def get_first_commit():
    """
    Retrieves the first commit hash in the Git repository.
    """
    try:
        first_commit = subprocess.run(
            ["git", "rev-list", "--max-parents=0", "HEAD"],
            capture_output=True, text=True
        ).stdout.strip()
        return first_commit
    except Exception as e:
        print("Error retrieving first commit:", e)
        return None

def track_file_with_git(md_file):
    """
    Adds and commits the Markdown file to Git.
    Shows word-by-word differences between the first and latest commit.
    Generates a diff report as a Markdown file.
    """
    repo = git.Repo(os.getcwd())

    # Add file to Git
    repo.git.add(md_file)

    # Check if there are changes before committing
    if repo.is_dirty():
        repo.index.commit(f"Updated {md_file}: {os.popen('date').read().strip()}")
        print(f"Changes in {md_file} committed.")

        # Get the first commit hash
        first_commit = get_first_commit()
        if first_commit:
            print("\nShowing changes since the first commit...\n")
            diff_output = subprocess.run(
                ["git", "diff", "--word-diff=color", first_commit, "HEAD", "--", md_file],
                capture_output=True, text=True
            ).stdout

            print(diff_output)

            # Save the diff report to a file
            generate_diff_report(md_file, first_commit)
            return diff_output
        else:
            print("No previous commits found. This is the first version.")
    else:
        print("No new changes detected.")


def generate_diff_report(md_file, first_commit):
    """
    Generates a Markdown report of the word-by-word differences 
    between the first commit and the latest version.
    """
    diff_output = subprocess.run(
        ["git", "diff", "--word-diff=porcelain", first_commit, "HEAD", "--", md_file],
        capture_output=True, text=True
    ).stdout

    report_filename = "diff_report.md"
    with open(report_filename, "w", encoding="utf-8") as report_file:
        report_file.write(f"# Document Change History: {md_file}\n\n")
        report_file.write("### Word-by-Word Changes Since First Commit\n")
        report_file.write("```\n")
        report_file.write(diff_output)
        report_file.write("```\n")

    print(f"\n📄 Changes saved in {report_filename}\n")

# if __name__ == "__main__":
#     if len(sys.argv) < 2:
#         print("Usage: python track_docx_full_history.py <filename.docx>")
#         sys.exit(1)

#     docx_file = sys.argv[1]

#     # Convert .docx to Markdown
#     md_file = convert_docx_to_md(docx_file)

#     # Initialize Git if not already initialized
#     initialize_git()

#     # Track and commit the converted Markdown file
#     track_file_with_git(md_file)

def process_docx(docx_file):
    """
    Runs the full document tracking process from another script.
    """
    md_file = convert_docx_to_md(docx_file)  # Convert .docx to .md
    initialize_git()  # Ensure Git is initialized
    return track_file_with_git(md_file)  # Track changes

