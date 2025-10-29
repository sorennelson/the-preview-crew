from dotenv import load_dotenv
load_dotenv()

from crewai import Agent, Crew, Process, Task, LLM
from crewai.utilities import printer
# Add orange to the color codes
if hasattr(printer, '_COLOR_CODES'):
    printer._COLOR_CODES['orange'] = '\033[38;5;208m'

from crewai.project import CrewBase, agent, crew, task, tool
from crewai_tools import SerperDevTool, ScrapeWebsiteTool, WebsiteSearchTool
from .tools.spotify_tool import SpotifyTool
from .tools.image_gen_tool import OpenAIImageGenerationTool
from .tools.spotify_preferences_tool import SpotifyTasteProfileTool, SpotifyUserDataToolInput
from typing import List
from datetime import datetime
from pydantic import BaseModel, Field
import os

# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators


RPM = int(os.getenv("RPM"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FILE_PATH = os.getenv("FILE_PATH")
OUTBOUND_FILE_PATH = os.getenv("OUTBOUND_FILE_PATH")
llm = LLM(
  model=os.getenv("MODEL"),
  max_tokens=int(os.getenv("TOKENS"))
)


@CrewBase
class ThePreview:
    """ThePreview crew with chat capability"""

    def __init__(self, spotify_token):
        # Queue for streaming updates
        self.stream_queue = None
        self._event_loop = None
        self.spotify_token = spotify_token

    def set_event_loop(self, loop):
        """Set the event loop for async usage (for streaming support)"""
        self._event_loop = loop

    def set_stream_queue(self, q):
        """Set the queue for streaming updates"""
        self.stream_queue = q

    def _stream_update(self, message: str, event_type: str = "task_update"):
        """Send update to stream queue if available"""
        if self.stream_queue:
            try:
                self._event_loop.call_soon_threadsafe(
                    lambda: self.stream_queue.put_nowait({'type': event_type, 'message': message})
                )
            except:
                pass

    def _task_callback(self, task_output):
        """Callback for task completion"""
        task_name = getattr(task_output, 'name', 'Unknown task')[:50]
        self._stream_update(f"{task_name}", "task_complete")

    def _step_callback(self, step_output):
        """Callback for agent steps"""
        # print(f"Step output:")
        # if hasattr(step_output, 'tool') and step_output.tool:
        #     tool = step_output.tool
        #     self._stream_update(f"{tool}", "step")
        return

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],
            verbose=True,
            tools=[
                SerperDevTool(),
                ScrapeWebsiteTool(),
            ],
            max_iter=10,
            max_rpm=RPM,
            llm=llm
        )

    @agent
    def playlist_creator(self) -> Agent:
        return Agent(
            config=self.agents_config["playlist_creator"],
            verbose=True,
            tools=[SpotifyTool(), SpotifyTasteProfileTool(self.spotify_token)],
            max_iter=10,
            max_rpm=RPM,
            llm=llm
        )

    @agent
    def image_generator(self) -> Agent:
        return Agent(
            config=self.agents_config["image_generator"],
            verbose=True,
            tools=[OpenAIImageGenerationTool(OPENAI_API_KEY, FILE_PATH, OUTBOUND_FILE_PATH)],
            max_iter=5,
            max_rpm=RPM,
            llm=llm
        )

    @agent
    def chat_agent(self) -> Agent:
        """Agent specifically for conversational interactions"""
        return Agent(
            role="Conversational Assistant",
            goal="Engage in natural conversation while maintaining context from previous messages. Provide helpful responses and remember what was discussed. Never return direct search results, always filter the results to maintain a normal conversation.",
            backstory="You're a friendly and knowledgeable assistant who helps users with their questions while maintaining conversation context. You can discuss previous topics and build upon earlier conversations.",
            verbose=True,
            max_iter=10,
            max_rpm=RPM,
            allow_delegation=True,
            llm=llm
        )

    @agent
    def manager(self) -> Agent:
        """Strategic Manager agent"""
        return Agent(
            config=self.agents_config["manager"],
            verbose=True,
            allow_delegation=False,
            max_iter=15,
            max_rpm=RPM,
            llm=llm
        )

    @task
    def web_scrape_task(self) -> Task:
        return Task(
            config=self.tasks_config["web_scrape_task"],
            output_file="logs/web_scrape.md",
            markdown=True,
        )

    @task
    def spotify_scrape_task(self) -> Task:
        return Task(
            config=self.tasks_config["spotify_scrape_task"],
            output_file="logs/spotify_topic_scrape.md",
        )

    @task
    def generate_image_task(self) -> Task:
        return Task(
            config=self.tasks_config["generate_image_task"],
            output_file="logs/generated_image.md",
            markdown=True,
        )

    @task
    def manager_task(self) -> Task:
        return Task(
            config=self.tasks_config["manager_task"],
            markdown=True,
        )

    def create_chat_task(self, message: str, session_id: str, chat_history: str = "") -> Task:
        """Create a task for chat interactions"""
        date = datetime.now().strftime("%B %d, %Y")
        print(date)
        return Task(
            name="Thinking",
            description=f"""
            Previous conversation:
            {chat_history or "Start of conversation"}
            
            Current message: {message}

            Respond naturally to the user's message while considering the conversation history.
            Delegate to your researcher as needed.
            If the message is about creating a playlist, delegate to the playlist workflow.
            If the message is about a new image, delegate to the image generator.
            Otherwise, provide a direct and helpful response.
            Keep the response as short as possible, don't overwhelm the user with a long response.
            """,
            expected_output="A natural, contextual response to the user's message.",
            agent=self.chat_agent(),
            markdown=True,
        )

    @crew
    def crew(self) -> Crew:
        """Creates the standard playlist/research crew"""
        return Crew(
            agents=[
              self.researcher(), self.playlist_creator(), self.image_generator(), self.manager()
            ], 
            tasks=[
              self.web_scrape_task(), self.spotify_scrape_task(), self.generate_image_task(), self.manager_task()
            ],
            process=Process.sequential, 
            verbose=True,
            task_callback=self._task_callback,
            step_callback=self._step_callback,
            max_rpm=RPM,
            output_log_file="logs/playlist_crew.md"
        )

    def chat_crew(self) -> Crew:
        """Creates a lightweight crew for chat interactions"""
        return Crew(
            agents=[self.chat_agent(), self.researcher(), self.playlist_creator(), self.image_generator()],
            tasks=[],  # Tasks will be added dynamically
            process=Process.sequential,
            verbose=True,
            step_callback=self._step_callback,
            max_rpm=RPM,
            output_log_file="logs/chat_crew.md",
        )