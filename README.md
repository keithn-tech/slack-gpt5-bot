# Slack GPT Bot with OpenAI Assistants API v2

A FastAPI-based Slack bot that uses OpenAI's Assistants API v2 with persistent memory. The bot maintains conversation context for each user using thread memory stored in a JSON file.

## Features

- 🤖 **OpenAI Assistants API v2**: Uses the latest OpenAI Assistants API with memory
- 💬 **Persistent Memory**: Maintains conversation context per user using `thread_memory.json`
- 🔄 **Asynchronous**: Built with `httpx.AsyncClient` for optimal performance
- 🛡️ **Security**: Slack signature verification for webhook security
- 📝 **Thread Support**: Responds in Slack threads to maintain conversation flow

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Copy the example environment file and configure your variables:

```bash
cp env.example .env
```

Edit `.env` with your actual values:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_ASSISTANT_ID=your_assistant_id_here

# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_SIGNING_SECRET=your_slack_signing_secret

# Server Configuration
HOST=0.0.0.0
PORT=8000
```

### 3. OpenAI Setup

1. **Get API Key**: Create an account at [OpenAI](https://platform.openai.com/) and get your API key
2. **Create Assistant**: Use the OpenAI API to create an assistant:
   ```bash
   curl https://api.openai.com/v1/assistants \
     -H "Authorization: Bearer $OPENAI_API_KEY" \
     -H "Content-Type: application/json" \
     -H "OpenAI-Beta: assistants=v2" \
     -d '{
       "name": "Slack Bot Assistant",
       "instructions": "You are a helpful assistant that responds to Slack messages.",
       "model": "gpt-4o-mini"
     }'
   ```
3. **Get Assistant ID**: Copy the assistant ID from the response and add it to your `.env` file

### 4. Slack Setup

1. **Create Slack App**: Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app
2. **Configure Bot Token**: Add the `chat:write` OAuth scope and install the app to your workspace
3. **Get Bot Token**: Copy the Bot User OAuth Token (starts with `xoxb-`)
4. **Configure Signing Secret**: Copy the Signing Secret from the Basic Information page
5. **Set Up Event Subscriptions**:
   - Enable Events
   - Set Request URL to: `https://your-domain.com/slack/events`
   - Subscribe to `app_mention` events
6. **Add Bot to Channels**: Invite the bot to channels where you want it to respond

### 5. Run the Bot

```bash
python app.py
```

Or using uvicorn directly:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

## Usage

1. **Mention the Bot**: In any channel where the bot is present, mention it with `@your-bot-name`
2. **Thread Memory**: The bot will remember your conversation history across sessions
3. **Threaded Responses**: The bot responds in the same thread to maintain context

## Architecture

### Key Components

- **ThreadMemory**: Manages persistent thread storage using `thread_memory.json`
- **OpenAIAssistant**: Handles all OpenAI Assistants API v2 interactions
- **SlackBot**: Manages Slack API communications
- **Memory Storage**: Uses `user_id` as the key to store thread IDs

### Memory Flow

1. User mentions bot → Extract `user_id` from Slack event
2. Check `thread_memory.json` for existing thread ID
3. If no thread exists → Create new OpenAI thread
4. Add user message to thread → Create and run assistant
5. Poll for completion → Retrieve and post response
6. Store thread ID in memory for future use

### File Structure

```
slack-gpt5-bot/
├── app.py                 # Main FastAPI application
├── requirements.txt       # Python dependencies
├── env.example           # Environment variables template
├── .env                  # Your environment variables (create this)
├── thread_memory.json    # Thread memory storage (auto-created)
└── README.md            # This file
```

## API Endpoints

- `POST /slack/events`: Handles Slack webhook events
- `GET /health`: Health check endpoint

## Security

- **Slack Signature Verification**: Validates incoming webhook requests
- **Environment Variables**: Sensitive data stored in `.env` file
- **Replay Attack Protection**: Checks request timestamps

## Error Handling

- Graceful handling of API failures
- Automatic error messages to Slack users
- Comprehensive logging for debugging

## Development

### Local Development

1. Use ngrok for local development:
   ```bash
   ngrok http 8000
   ```

2. Update your Slack app's Request URL with the ngrok URL

3. Set up your `.env` file with local values

### Testing

The bot includes a health check endpoint at `/health` for monitoring.

## Troubleshooting

### Common Issues

1. **"Invalid signature"**: Check your `SLACK_SIGNING_SECRET`
2. **"Slack API error"**: Verify your `SLACK_BOT_TOKEN` and bot permissions
3. **"OpenAI API error"**: Check your `OPENAI_API_KEY` and `OPENAI_ASSISTANT_ID`
4. **Memory not persisting**: Ensure `thread_memory.json` is writable

### Logs

Check the console output for detailed error messages and debugging information.

## License

This project is open source and available under the MIT License. 