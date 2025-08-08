import os
import json
import asyncio
from typing import Dict, Optional
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import httpx
from dotenv import load_dotenv
import hmac
import hashlib
import time

# Load environment variables
load_dotenv()

app = FastAPI(title="Slack GPT Bot", version="1.0.0")

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

# Memory file path
MEMORY_FILE = "thread_memory.json"

class ThreadMemory:
    """Helper class to manage thread memory storage"""
    
    @staticmethod
    def load_memory() -> Dict[str, str]:
        """Load thread memory from JSON file"""
        try:
            if os.path.exists(MEMORY_FILE):
                with open(MEMORY_FILE, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error loading memory: {e}")
            return {}
    
    @staticmethod
    def save_memory(memory: Dict[str, str]) -> None:
        """Save thread memory to JSON file"""
        try:
            with open(MEMORY_FILE, 'w') as f:
                json.dump(memory, f, indent=2)
        except Exception as e:
            print(f"Error saving memory: {e}")
    
    @staticmethod
    def get_thread_id(user_id: str) -> Optional[str]:
        """Get thread ID for a user"""
        memory = ThreadMemory.load_memory()
        return memory.get(user_id)
    
    @staticmethod
    def set_thread_id(user_id: str, thread_id: str) -> None:
        """Set thread ID for a user"""
        memory = ThreadMemory.load_memory()
        memory[user_id] = thread_id
        ThreadMemory.save_memory(memory)

class OpenAIAssistant:
    """Helper class to interact with OpenAI Assistants API"""
    
    def __init__(self):
        self.api_key = OPENAI_API_KEY
        self.assistant_id = OPENAI_ASSISTANT_ID
        self.base_url = "https://api.openai.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "assistants=v2"
        }
    
    async def create_thread(self) -> str:
        """Create a new thread"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/threads",
                headers=self.headers,
                json={}
            )
            response.raise_for_status()
            return response.json()["id"]
    
    async def add_message(self, thread_id: str, content: str) -> str:
        """Add a message to a thread"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/threads/{thread_id}/messages",
                headers=self.headers,
                json={
                    "role": "user",
                    "content": content
                }
            )
            response.raise_for_status()
            return response.json()["id"]
    
    async def create_run(self, thread_id: str) -> str:
        """Create a run for a thread"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/threads/{thread_id}/runs",
                headers=self.headers,
                json={
                    "assistant_id": self.assistant_id
                }
            )
            response.raise_for_status()
            return response.json()["id"]
    
    async def get_run_status(self, thread_id: str, run_id: str) -> str:
        """Get the status of a run"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/threads/{thread_id}/runs/{run_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()["status"]
    
    async def get_messages(self, thread_id: str) -> list:
        """Get messages from a thread"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/threads/{thread_id}/messages",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()["data"]
    
    async def wait_for_run_completion(self, thread_id: str, run_id: str, timeout: int = 60) -> bool:
        """Wait for a run to complete"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = await self.get_run_status(thread_id, run_id)
            if status == "completed":
                return True
            elif status in ["failed", "cancelled", "expired"]:
                return False
            await asyncio.sleep(1)
        return False

class SlackBot:
    """Helper class to interact with Slack API"""
    
    def __init__(self):
        self.bot_token = SLACK_BOT_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json"
        }
    
    async def post_message(self, channel: str, thread_ts: str, text: str) -> None:
        """Post a message to a Slack thread"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers=self.headers,
                json={
                    "channel": channel,
                    "thread_ts": thread_ts,
                    "text": text
                }
            )
            response.raise_for_status()
            result = response.json()
            if not result.get("ok"):
                raise Exception(f"Slack API error: {result.get('error')}")

def verify_slack_signature(request: Request) -> bool:
    """Verify Slack request signature"""
    if not SLACK_SIGNING_SECRET:
        return True  # Skip verification if no secret configured
    
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    
    if not timestamp or not signature:
        return False
    
    # Check if request is too old (replay attack protection)
    if abs(int(time.time()) - int(timestamp)) > 60 * 5:
        return False
    
    # Verify signature
    body = request.body()
    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    expected_signature = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)

# Initialize helper classes
openai_assistant = OpenAIAssistant()
slack_bot = SlackBot()

@app.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    """Handle Slack events"""
    # Verify Slack signature
    if not verify_slack_signature(request):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse the request body
    body = await request.json()
    
    # Handle URL verification challenge
    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge")}
    
    # Handle events
    if body.get("type") == "event_callback":
        event = body.get("event", {})
        
        # Only process app_mention events
        if event.get("type") == "app_mention":
            background_tasks.add_task(process_app_mention, event)
    
    return {"status": "ok"}

async def process_app_mention(event: dict):
    """Process app mention events"""
    try:
        # Extract event data
        user_id = event.get("user")
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        text = event.get("text", "")
        
        # Remove bot mention from text
        # Assuming bot is mentioned with @bot_name
        text = text.split(">", 1)[1].strip() if ">" in text else text
        
        if not text:
            return
        
        # Get or create thread ID for this user
        thread_id = ThreadMemory.get_thread_id(user_id)
        if not thread_id:
            thread_id = await openai_assistant.create_thread()
            ThreadMemory.set_thread_id(user_id, thread_id)
        
        # Add user message to thread
        await openai_assistant.add_message(thread_id, text)
        
        # Create and run assistant
        run_id = await openai_assistant.create_run(thread_id)
        
        # Wait for run completion
        success = await openai_assistant.wait_for_run_completion(thread_id, run_id)
        
        if success:
            # Get the latest assistant message
            messages = await openai_assistant.get_messages(thread_id)
            
            # Find the latest assistant message
            assistant_messages = [msg for msg in messages if msg["role"] == "assistant"]
            if assistant_messages:
                latest_message = assistant_messages[0]  # Messages are ordered newest first
                content = latest_message["content"][0]["text"]["value"]
                
                # Post response to Slack
                await slack_bot.post_message(channel, thread_ts, content)
            else:
                await slack_bot.post_message(channel, thread_ts, "I'm sorry, I couldn't generate a response.")
        else:
            await slack_bot.post_message(channel, thread_ts, "I'm sorry, there was an error processing your request.")
    
    except Exception as e:
        print(f"Error processing app mention: {e}")
        # Try to post error message to Slack
        try:
            channel = event.get("channel")
            thread_ts = event.get("thread_ts") or event.get("ts")
            await slack_bot.post_message(channel, thread_ts, "I'm sorry, there was an error processing your request.")
        except:
            pass

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True
    ) 