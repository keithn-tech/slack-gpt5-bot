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
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI(title="Slack GPT Bot", version="1.0.0")

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

# Log configuration status
logger.info(f"OpenAI API Key configured: {'Yes' if OPENAI_API_KEY else 'No'}")
logger.info(f"OpenAI Assistant ID configured: {'Yes' if OPENAI_ASSISTANT_ID else 'No'}")
logger.info(f"Slack Bot Token configured: {'Yes' if SLACK_BOT_TOKEN else 'No'}")
logger.info(f"Slack Signing Secret configured: {'Yes' if SLACK_SIGNING_SECRET else 'No'}")

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
            logger.error(f"Error loading memory: {e}")
            return {}
    
    @staticmethod
    def save_memory(memory: Dict[str, str]) -> None:
        """Save thread memory to JSON file"""
        try:
            with open(MEMORY_FILE, 'w') as f:
                json.dump(memory, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
    
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
        """Post a message to a Slack channel or thread"""
        message_data = {
            "channel": channel,
            "text": text
        }
        
        # Only add thread_ts if it's provided (for threading)
        if thread_ts:
            message_data["thread_ts"] = thread_ts
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers=self.headers,
                json=message_data
            )
            response.raise_for_status()
            result = response.json()
            if not result.get("ok"):
                raise Exception(f"Slack API error: {result.get('error')}")

async def verify_slack_signature(request: Request, body: bytes = None) -> bool:
    """Verify Slack request signature"""
    if not SLACK_SIGNING_SECRET:
        logger.warning("No Slack signing secret configured, skipping verification")
        return True  # Skip verification if no secret configured
    
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    
    if not timestamp or not signature:
        logger.warning("Missing Slack signature headers")
        return False
    
    # Check if request is too old (replay attack protection)
    if abs(int(time.time()) - int(timestamp)) > 60 * 5:
        logger.warning("Request timestamp too old")
        return False
    
    # Verify signature
    if body is None:
        body = await request.body()  # ✅ FIXED: await the body
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

logger.info("=== Slack GPT Bot Starting ===")
logger.info(f"OpenAI API Key configured: {'Yes' if OPENAI_API_KEY else 'No'}")
logger.info(f"OpenAI Assistant ID configured: {'Yes' if OPENAI_ASSISTANT_ID else 'No'}")
logger.info(f"Slack Bot Token configured: {'Yes' if SLACK_BOT_TOKEN else 'No'}")
logger.info(f"Slack Signing Secret configured: {'Yes' if SLACK_SIGNING_SECRET else 'No'}")
logger.info("=== Bot initialization complete ===")

@app.get("/")
async def root():
    """Root endpoint for health check"""
    logger.info("Root endpoint accessed")
    return {
        "status": "healthy",
        "message": "Slack GPT Bot is running",
        "openai_configured": bool(OPENAI_API_KEY and OPENAI_ASSISTANT_ID),
        "slack_configured": bool(SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET)
    }

@app.get("/test")
async def test():
    """Simple test endpoint"""
    logger.info("Test endpoint accessed")
    return {"message": "Bot is running", "timestamp": time.time()}

@app.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    """Handle Slack events"""
    logger.info("Received Slack event")
    
    # Get the raw body for signature verification
    raw_body = await request.body()
    
    # Verify Slack signature first
    if not await verify_slack_signature(request, raw_body):
        logger.error("Invalid Slack signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse the request body from the raw body we already have
    import json
    body = json.loads(raw_body.decode())
    logger.info(f"SLACK EVENT RECEIVED: {body}")
    logger.info(f"Event type: {body.get('type')}")
    
    # Handle URL verification challenge
    if body.get("type") == "url_verification":
        logger.info("Handling URL verification challenge")
        return {"challenge": body.get("challenge")}
    
    # Handle events
    if body.get("type") == "event_callback":
        event = body.get("event", {})
        
        # Only process app_mention events
        if event.get("type") == "app_mention":
            logger.info("Processing app mention event")
            background_tasks.add_task(process_app_mention, event)
    
    return {"status": "ok"}

async def process_app_mention(event: dict):
    """Process app mention events"""
    try:
        logger.info("Starting to process app mention")
        
        # Extract event data
        user_id = event.get("user")
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        text = event.get("text", "")
        
        logger.info(f"Processing message from user {user_id} in channel {channel}")
        
        # Remove bot mention from text
        # Assuming bot is mentioned with @bot_name
        text = text.split(">", 1)[1].strip() if ">" in text else text
        
        if not text:
            logger.warning("Empty message text")
            return
        
        # Get or create thread ID for this user
        thread_id = ThreadMemory.get_thread_id(user_id)
        if not thread_id:
            logger.info(f"Creating new thread for user {user_id}")
            thread_id = await openai_assistant.create_thread()
            ThreadMemory.set_thread_id(user_id, thread_id)
        else:
            logger.info(f"Using existing thread {thread_id} for user {user_id}")
        
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
                await slack_bot.post_message(channel, None, content)
                logger.info("Successfully posted response to Slack")
            else:
                await slack_bot.post_message(channel, None, "I'm sorry, I couldn't generate a response.")
                logger.warning("No assistant message found")
        else:
            await slack_bot.post_message(channel, None, "I'm sorry, there was an error processing your request.")
            logger.error("Run failed to complete")
    
    except Exception as e:
        logger.error(f"Error processing app mention: {e}")
        # Try to post error message to Slack
        try:
            channel = event.get("channel")
            await slack_bot.post_message(channel, None, "I'm sorry, there was an error processing your request.")
        except:
            logger.error("Failed to post error message to Slack")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "openai_configured": bool(OPENAI_API_KEY and OPENAI_ASSISTANT_ID),
        "slack_configured": bool(SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET)
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=False  # Disable reload in production
    ) 