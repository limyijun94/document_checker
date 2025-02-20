import requests
from openai import AsyncAzureOpenAI
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_version = os.getenv("AZURE_OPENAI_API_VERSION")
weather_api_key = os.getenv("WEATHER_API")  # Ensure this is set in your .env file

client = AsyncAzureOpenAI(
   azure_endpoint=azure_endpoint,
   api_version=api_version,
   api_key=api_key
)

model = OpenAIModel('gpt-4o-mini', openai_client=client)

class Deps(BaseModel):
   weather_api_key: str | None = Field(title='Weather API Key', description='Weather service API key')
   geo_api_key: str | None = Field(title='Geo API Key', description='Geo service API key')

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
   
   response = requests.get(
        f"http://api.weatherapi.com/v1/current.json?key={weather_api_key}&q={location_description}&aqi=no"
    )
   if response.status_code == 200:
        data = response.json()
        if data:
            location = data['location']
            return {"lat": location['lat'], 'lng': location['lon']}
        
        else:
            raise ModelRetry(f'Error fetching location: {response.status_code}')

@weather_agent.tool
def get_weather(
   ctx: RunContext[Deps], lat: float, lng: float
) -> dict[str, any]:
   if lat == 0 and lng == 0:
       raise ModelRetry('Could not find the location')

   params = {
       'q': f"{lat},{lng}",
       'key': ctx.deps.weather_api_key
   }

   # Fetch current weather using WeatherAPI
   response = requests.get(
       f"http://api.weatherapi.com/v1/current.json?key={weather_api_key}&q={lat},{lng}&aqi=no"
   )
   if response.status_code == 200:
       data = response.json()
       current_weather = data['current']
       return {
           'temperature': current_weather['temp_c'],
           'condition': current_weather['condition']['text'],
           'humidity': current_weather['humidity'],
           'wind_speed': current_weather['wind_kph'],
           'feels_like': current_weather['feelslike_c']
       }
   else:
       raise ModelRetry(f'Error fetching weather data: {response.status_code}')

if __name__ == '__main__':
   deps = Deps(weather_api_key=weather_api_key, geo_api_key=weather_api_key) 
   result = weather_agent.run_sync(
       'What is the weather like in Singapore, London, Johor, Florida, and Florence?',
       deps=deps
   )

   print('---')
   print('Result')
   print(result.data)
