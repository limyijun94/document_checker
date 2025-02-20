import requests
from openai import AsyncAzureOpenAI
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv
import asyncio
from duckduckgo_search import DDGS, AsyncDDGS
import datetime

load_dotenv()

api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_version = os.getenv("AZURE_OPENAI_API_VERSION")
weather_api_key = os.getenv("WEATHER_API")

client = AsyncAzureOpenAI(
   azure_endpoint=azure_endpoint,
   api_version=api_version,
   api_key=api_key
)

model = OpenAIModel('gpt-4o-mini', openai_client=client)

class Deps(BaseModel):
   weather_api_key: str | None = Field(title='Weather API Key', description='Weather service API key')
   geo_api_key: str | None = Field(title='Geo API Key', description='Geo service API key')
   date: str


######### WEATHER AGENT ##########

weather_agent = Agent(
   name='Weather Agent',
   model=model,
   system_prompt=(
       'Be concise, and reply with a short paragraph.'
       'Use the `get_lat_lng` tool to get the latitude and longitude of the location.'
       'Then use the `get_weather` tool to get weather.'
   ),
   deps_type=Deps,
   # result_type=<responseobject>
)

@weather_agent.tool
def get_lat_lng(
   ctx: RunContext[Deps], location_description: str
) -> dict[str, float]:
   params = {
       'q': location_description,
       'key': ctx.deps.geo_api_key
   }
   print('Params passed by agent:', location_description)
   response = requests.get(f"http://api.weatherapi.com/v1/current.json?key={weather_api_key}&q={location_description}&aqi=no")
   data = response.json()
   location = data['location']
   
   return {"lat": location['lat'], 'lng': location['lon']}
 
@weather_agent.tool
def get_weather(
   ctx: RunContext[Deps], lat: float, lng: float
) -> dict[str, any]:
   params = {
       'q': f"{lat},{lng}",
       'key': ctx.deps.weather_api_key
   }
   response = requests.get(f"http://api.weatherapi.com/v1/current.json?key={weather_api_key}&q={lat},{lng}&aqi=no")
   data = response.json()
   current_weather = data['current']
   return {
        'temperature': current_weather['temp_c'],
        'condition': current_weather['condition']['text'],
        'humidity': current_weather['humidity'],
        'wind_speed': current_weather['wind_kph'],
        'feels_like': current_weather['feelslike_c']
    }

#################### Main Agent #########################
math_agent = Agent(
   name='Math Agent',
   model=model,
   system_prompt=(
       'You are a math genius, capable of solving complex equations and explaining to the user as if they were 5.'), 
       deps_type=Deps)

#################### Web Agent #########################

web_agent = Agent(
   name='Web Agent',
   model=model,
   system_prompt=(
       'You are an expert in searching for information and will find all relevant ones from sites to answer a query'), 
       deps_type=Deps)

@web_agent.tool
async def get_DDGS_results(ctx: RunContext[Deps], query: str) -> str:
   print(f"Searching for: {query}")
   results = await AsyncDDGS(proxy=None).atext(query, max_results=10)
   return results

#################### Main Agent #########################
main_agent = Agent(
   name='Main Agent',
   model=model,
   system_prompt=(
       '''You are a helpful assistant, capable of delegating tasks to other more specialized agents. 
      You must note the present date using the `find_current_date` tool, before determining what other tools to use.'''),
       deps_type=Deps)

@main_agent.tool
async def delegate_to_weather_agent(ctx: RunContext[Deps],location:str) -> str:
   print(f"Delegating to weather agent for {location}")
   result = await weather_agent.run(f"What is the weather in {location}", message_history=message_history,deps=ctx.deps)
   return result.data

@main_agent.tool_plain
async def delegate_to_math_agent(expression:str) -> str:
   print(f"Delegating to math agent for {expression}")
   result = await math_agent.run(f"Calculate {expression}")
   return result.data

@main_agent.tool
async def delegate_to_web_agent(ctx: RunContext[Deps], query:str) -> str:
   print(f"Delegating to web agent for {query}")
   result = await web_agent.run(f"Find information on {query}", message_history=message_history, deps=ctx.deps)
   return result.data

@main_agent.tool
async def find_current_date(ctx: RunContext[Deps]) -> str:
   print(f"Finding current date..")
   current_date = ctx.deps.date
   return current_date

######### Get Current Date ##########
current_date = datetime.date.today()
date_string = current_date.strftime("%Y-%m-%d")

message_history = []
while True:
   current_message = input('You: ')
   if current_message == 'quit':
      break
   deps = Deps(weather_api_key=weather_api_key, geo_api_key=weather_api_key,date=date_string) 
   result = main_agent.run_sync(current_message, message_history=message_history, deps=deps)
   message_history = result.new_messages()
   print(f"Response: {result.data}")



# if __name__ == '__main__':
#    deps = Deps(weather_api_key=weather_api_key, geo_api_key=weather_api_key) 
#    result = weather_agent.run_sync(
#        'What is the weather like in Singapore, London, Johor, Florida, and Florence?',
#        deps=deps
#    )

#    print('---')
#    print('Result')
#    print(result.data)
