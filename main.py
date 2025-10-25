from src.the_preview.crew import ThePreview
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import uuid, os, json, asyncio, re

app = FastAPI()

# Create static directory if it doesn't exist
Path("./files/images").mkdir(parents=True, exist_ok=True)
# Mount static files directory at /files to match URL structure
app.mount("/files", StaticFiles(directory="./files"), name="files")

# CORS middleware for Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://the-preview-beta.vercel.app/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store conversation sessions (use Redis in production)
sessions: Dict[str, Dict] = {}
SESSION_TIMEOUT = timedelta(hours=1)

# Initialize crew instance
crew_instance = ThePreview()

test_result = """
# The Matrix:

**Songs**

1.  [Nine Inch Nails: Closer](https://open.spotify.com/track/5mc6EyF1OIEOhAkD0Gg9Lc)
2.  [Massive Attack: Teardrop](https://open.spotify.com/track/67Hna13dNDkZvBpTXRIaOJ)
3.  [The Prodigy: Firestarter](https://open.spotify.com/track/1auX4gkGe7hbrOH0BXdpV4)
4.  [The Crystal Method: Busy Child](https://open.spotify.com/track/43F49A8ReVXhH7l0jGMViS)
5.  [Underworld: Born Slippy (Nuxx)](https://open.spotify.com/track/7xQYVjs4wZNdCwO0EeAWMC)
6.  [Rob Zombie: Dragula](https://open.spotify.com/track/6Nm8h73ycDG2saCnZV8poF)
7.  [Portishead: Glory Box](https://open.spotify.com/track/3Ty7OTBNSigGEpeW2PqcsC)
8.  [Crystal Waters: 100% Pure Love](https://open.spotify.com/track/66X03EIfE1zm99rd4SfL71)
9.  [Robert Plant: If I Were a Carpenter - 2006 Remaster](https://open.spotify.com/track/1zU2sDGmJUNhr5z0EXuVcV)
10. [Faithless: Muhammad Ali 2.0 - High Contrast Remix](https://open.spotify.com/track/4j5ZVdfUro5N07sSwI38bi)

**Podcasts**

1.  [Conversations with Composers: David Robertson on Conducting, Pierre Boulez, and Musical Interpretation](https://open.spotify.com/episode/0ittvsTALuQMtxvVoM4JGO)
2.  [All Songs Considered: A conversation with David Gilmour](https://open.spotify.com/episode/3YZPUqme3U5kPbJOPjadpN)
3.  [Sound Plus Doctrine: Hard Conversations With Your Musicians](https://open.spotify.com/episode/5dKZ8MvrFXp1WSI2wL3lHg)
4.  [Alt.Latino: A conversation with Gloria Estefan](https://open.spotify.com/episode/5fIyabSS3C9PNxLggRBVpt)
5.  [Every Little Thing: Episode 11: The Composer's Unheard Score](https://open.spotify.com/episode/4RcXWMKHVHGAHJW7gFqmxf)
6.  [SmartLess: "Gustavo Dudamel"](https://open.spotify.com/episode/2x0MttVPoVX72a1zMuPWhh)
7.  [Switched on Pop: The classical rebel who infiltrated pop music](https://open.spotify.com/episode/1QWXgk4V4P3HZigwA66j8f)
8.  [Lex Fridman Podcast: Lex Fridman Podcast](https://open.spotify.com/show/2MAi0BvDc6GTFvKFPXnkCL)
9.  [Philosophize This!: Philosophize This!](https://open.spotify.com/show/2Shpxw7dPoxRJCdfFXTWLE)
10. [Radiolab: Radiolab](https://open.spotify.com/show/2hmkzUtix0qTqvtpPcMzEL)
<IMAGE:http://localhost:8000/files/images/0e1586ae2d1e84b542491be1f1c07bc5.png>  
"""

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    mode: str = "auto"  # "auto", "chat", "playlist"
    image_url: Optional[str] = None  # For image inputs
    stream: bool = False  # Enable streaming

class ChatResponse(BaseModel):
    response: str
    session_id: str
    mode: str
    timestamp: str
    images: Optional[List[str]] = None  # For image outputs (URLs)

class ConversationHistory(BaseModel):
    messages: List[Dict[str, Any]]

def cleanup_old_sessions():
    """Remove sessions older than timeout"""
    current_time = datetime.now()
    expired = [
        sid for sid, data in sessions.items()
        if current_time - data['last_active'] > SESSION_TIMEOUT
    ]
    for sid in expired:
        del sessions[sid]

def get_or_create_session(session_id: Optional[str] = None) -> str:
    """Get existing session or create new one"""
    cleanup_old_sessions()
    
    # If session_id is provided, try to use it
    if session_id:
        if session_id in sessions:
            # Existing session - update last active time
            sessions[session_id]['last_active'] = datetime.now()
            return session_id
        else:
            # Session ID provided but doesn't exist - create with that ID
            sessions[session_id] = {
                'created': datetime.now(),
                'last_active': datetime.now(),
                'messages': []
            }
            return session_id
    
    # No session_id provided - create new one
    new_session_id = str(uuid.uuid4())
    sessions[new_session_id] = {
        'created': datetime.now(),
        'last_active': datetime.now(),
        'messages': []
    }
    return new_session_id

def detect_intent(message: str) -> str:
    """Detect if user wants a playlist or just wants to chat"""
    playlist_keywords = [
        'create playlist', 'make playlist', 'create a playlist', 'make a playlist',
        'make me a playlist', 'create for me a playlist', 'create me a playlist'
        'songs for', 'music for', 'podcasts for', 'recommendations'
    ]
    
    message_lower = message.lower()
    if any(keyword in message_lower for keyword in playlist_keywords):
        return "playlist"
    return "chat"

def extract_images_from_result(result: any) -> tuple[str, List[str]]:
    """Extract image URLs from CrewAI result and return cleaned text + images"""
    images = []
    
    # Get the result as string
    result_str = str(result.raw) if hasattr(result, 'raw') else str(result)
    
    # Extract images in <IMAGE:url> format
    image_pattern = r'<IMAGE:(.*?)>'
    found_images = re.findall(image_pattern, result_str)
    images.extend(found_images)
    
    # Remove <IMAGE:url> tags from the text
    cleaned_text = re.sub(image_pattern, '', result_str).strip()
    
    # Also find markdown images: ![alt](url)
    markdown_images = re.findall(r'!\[.*?\]\((.*?)\)', cleaned_text)
    images.extend(markdown_images)
    
    # Find raw URLs that look like images
    image_urls = re.findall(
        r'https?://[^\s<>"]+\.(?:jpg|jpeg|png|gif|webp|svg)',
        cleaned_text,
        re.IGNORECASE
    )
    images.extend(image_urls)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_images = []
    for img in images:
        if img not in seen:
            seen.add(img)
            unique_images.append(img)
    
    return cleaned_text, unique_images

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(chat_message: ChatMessage):
    """Handle both chat and playlist requests"""

        # If streaming is enabled, return streaming response
    if chat_message.stream:
        return StreamingResponse(
            stream_crew_progress(chat_message),
            media_type="text/event-stream"
        )

    try:
        session_id = get_or_create_session(chat_message.session_id)
        session = sessions[session_id]
        
        print(f"📝 Session ID: {session_id}")
        print(f"📊 Current message count: {len(session['messages'])}")
        
        # Store user message with optional image
        user_msg = {
            'role': 'user',
            'content': chat_message.message,
            'timestamp': datetime.now().isoformat()
        }
        if chat_message.image_url:
            user_msg['image_url'] = chat_message.image_url
        
        session['messages'].append(user_msg)
        
        # Determine mode
        if chat_message.mode == "auto":
            mode = detect_intent(chat_message.message)
        else:
            mode = chat_message.mode
        
        print(f"🎯 Mode detected: {mode}")
        
        # Build chat history context (exclude current message)
        chat_history = "\n".join([
            f"{msg['role'].title()}: {msg['content']}"
            for msg in session['messages'][:-1]
        ])
        
        print(f"💬 Chat history length: {len(chat_history)} chars")
        
        # Prepare inputs with image if provided
        crew_inputs = {
            'subject': chat_message.message,
            'date': datetime.now().strftime("%B %d, %Y")
        }
        if chat_message.image_url:
            crew_inputs['image_url'] = chat_message.image_url
        
        # Execute appropriate crew workflow
        images = []
        if mode == "playlist":
            # Run full playlist crew
            result = crew_instance.crew().kickoff(inputs=crew_inputs)
            response = str(result.raw) if hasattr(result, 'raw') else str(result)
            response, images = extract_images_from_result(result)
        else:
            # Run lightweight chat crew
            chat_crew = crew_instance.chat_crew(session_id)
            chat_task = crew_instance.create_chat_task(
                message=chat_message.message,
                session_id=session_id,
                chat_history=chat_history
            )
            chat_crew.tasks = [chat_task]
            result = chat_crew.kickoff(inputs=crew_inputs)
            response = str(result.raw) if hasattr(result, 'raw') else str(result)
            response, images = extract_images_from_result(result)
        
        # Store assistant response with images
        assistant_msg = {
            'role': 'assistant',
            'content': response,
            'timestamp': datetime.now().isoformat()
        }
        if images:
            assistant_msg['images'] = images
        
        session['messages'].append(assistant_msg)
        
        print(f"✅ Total messages now: {len(session['messages'])}")
        print(f"🖼️  Images in response: {len(images)}")
        
        return ChatResponse(
            response=response,
            session_id=session_id,
            mode=mode,
            timestamp=datetime.now().isoformat(),
            images=images if images else None
        )
        
    except Exception as e:
        if session['messages'] and session['messages'][-1]['role'] == 'user':
            session['messages'].pop()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def stream_crew_progress(chat_message: ChatMessage):
    """Stream CrewAI progress updates as SSE with async queue."""
    
    session_id = get_or_create_session(chat_message.session_id)
    session = sessions[session_id]

    main_loop = asyncio.get_running_loop()
    crew_instance.set_event_loop(main_loop)

    # Store user message
    user_msg = {
        'role': 'user',
        'content': chat_message.message,
        'timestamp': datetime.now().isoformat()
    }
    session['messages'].append(user_msg)

    # Send initial connected message
    yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"
    await asyncio.sleep(0)  # allow event loop to flush

    # Determine mode
    mode = detect_intent(chat_message.message) if chat_message.mode == "auto" else chat_message.mode
    print(f"Intent: {mode}")

    yield f"data: {json.dumps({'type': 'mode', 'mode': mode})}\n\n"
    await asyncio.sleep(0)

    # Async queue for streaming updates
    update_queue = asyncio.Queue()
    crew_instance.set_stream_queue(update_queue)

    def run_crew():
        """Run CrewAI in background thread and push updates to async queue."""
        try:
            crew_inputs = {
                'subject': chat_message.message,
                'date': datetime.now().strftime("%B %d, %Y")
            }

            print("Running crew")
            if mode == "playlist":
                result = crew_instance.crew().kickoff(inputs=crew_inputs)
            else:
                chat_history = "\n".join(
                    f"{msg['role'].title()}: {msg['content']}" 
                    for msg in session['messages'][:-1]
                )
                chat_crew = crew_instance.chat_crew(session_id)
                chat_task = crew_instance.create_chat_task(
                    message=chat_message.message,
                    session_id=session_id,
                    chat_history=chat_history
                )
                chat_crew.tasks = [chat_task]
                result = chat_crew.kickoff(inputs=crew_inputs)

            # push completion signal
            main_loop.call_soon_threadsafe(
                update_queue.put_nowait, {'type': 'crew_done', 'result': result}
            )

        except Exception as e:
            main_loop.call_soon_threadsafe(
                update_queue.put_nowait, {'type': 'error', 'error': str(e)}
            )

    # Start crew in background
    main_loop.run_in_executor(None, run_crew)

    # Stream updates
    while True:
        update = await update_queue.get()

        if update['type'] == 'crew_done':
            result = update['result']
            response, images = extract_images_from_result(result)

            # Store assistant message
            assistant_msg = {
                'role': 'assistant',
                'content': response,
                'timestamp': datetime.now().isoformat(),
                'mode': mode
            }
            if images:
                assistant_msg['images'] = images
            session['messages'].append(assistant_msg)

            yield f"data: {json.dumps({'type': 'complete', 'response': response, 'images': images, 'session_id': session_id, 'timestamp': datetime.now().isoformat()})}\n\n"
            break

        elif update['type'] == 'error':
            yield f"data: {json.dumps(update)}\n\n"
            break

        else:
            yield f"data: {json.dumps(update)}\n\n"
            await asyncio.sleep(0)  # allow loop to flush

    # Cleanup
    crew_instance.set_stream_queue(None)

@app.get("/api/history/{session_id}", response_model=ConversationHistory)
async def get_history(session_id: str):
    """Retrieve conversation history for a session"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return ConversationHistory(messages=sessions[session_id]['messages'])

@app.delete("/api/session/{session_id}")
async def clear_session(session_id: str):
    """Clear a conversation session"""
    if session_id in sessions:
        del sessions[session_id]
    return {"message": "Session cleared"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "active_sessions": len(sessions)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)