from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests
import json
import os
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load config on startup
    config = load_config()
    if config.get("active_key"):
        current_config["api_key"] = config["active_key"]
    yield

app = FastAPI(title="Clawbook for Humans", lifespan=lifespan)

# Setup paths
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Mount static files
app.mount("/assets", StaticFiles(directory=BASE_DIR / "assets"), name="assets")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Constants
API_BASE = "https://www.moltbook.com/api/v1"
CONFIG_FILE = Path(__file__).parent / "credentials.json"

# State
current_config = {"api_key": None}

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Migration if it's the old format (dict but not list)
                if isinstance(config, dict) and "api_key" in config and "agents" not in config:
                    new_config = {
                        "active_key": config["api_key"],
                        "agents": [config]
                    }
                    save_config(new_config)
                    return new_config
                return config
        except:
            return {"active_key": None, "agents": []}
    return {"active_key": None, "agents": []}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def add_agent_to_config(agent_data):
    config = load_config()
    agents = config.get("agents", [])
    
    # Check if exists, update or add
    found = False
    for i, a in enumerate(agents):
        if a.get("api_key") == agent_data.get("api_key"):
            agents[i] = agent_data
            found = True
            break
    
    if not found:
        agents.append(agent_data)
    
    config["agents"] = agents
    config["active_key"] = agent_data.get("api_key")
    save_config(config)
    current_config["api_key"] = config["active_key"]

def get_session(api_key: str):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    return s

@app.get("/post", response_class=HTMLResponse)
async def post_page(request: Request):
    api_key = current_config.get("api_key")
    if not api_key:
        return RedirectResponse(url="/login")
    
    submolts = []
    s = get_session(api_key)
    try:
        res = s.get(f"{API_BASE}/submolts")
        if res.status_code == 200:
            data = res.json()
            # Try to find the list in common response keys
            submolts = data.get("submolts") or data.get("data", {}).get("submolts") or []
    except Exception as e:
        print(f"Error fetching submolts: {e}")

    return templates.TemplateResponse("post.html", {
        "request": request, 
        "submolts": submolts
    })

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    config = load_config()
    api_key = current_config.get("api_key")
    agent_info = None
    status_info = None
    
    if api_key:
        s = get_session(api_key)
        try:
            # Get stats
            res = s.get(f"{API_BASE}/agents/me")
            if res.status_code == 200:
                agent_info = res.json().get("agent")
            
            # Get status
            res_status = s.get(f"{API_BASE}/agents/status")
            if res_status.status_code == 200:
                status_info = res_status.json()
        except:
            pass

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "agent": agent_info, 
        "status": status_info,
        "api_key": api_key,
        "saved_agents": config.get("agents", [])
    })

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(api_key: str = Form(...)):
    s = get_session(api_key)
    agent_name = "Unknown"
    try:
        res = s.get(f"{API_BASE}/agents/me")
        if res.status_code == 200:
            agent_name = res.json().get("agent", {}).get("name")
    except:
        pass

    add_agent_to_config({
        "api_key": api_key,
        "agent_name": agent_name
    })
        
    return RedirectResponse(url="/", status_code=303)

@app.post("/add-agent")
async def add_agent(request: Request, api_key: str = Form(...)):
    """Add an existing agent using API key"""
    s = get_session(api_key)
    agent_name = "Unknown"
    config = load_config()
    try:
        res = s.get(f"{API_BASE}/agents/me")
        if res.status_code == 200:
            agent_name = res.json().get("agent", {}).get("name")
            # Successfully verified the API key, add it to config
            add_agent_to_config({
                "api_key": api_key,
                "agent_name": agent_name
            })
            return RedirectResponse(url="/", status_code=303)
        else:
            # Return to index with error
            return templates.TemplateResponse("index.html", {
                "request": request,
                "api_key": current_config.get("api_key"),
                "error": "Invalid API key or agent not found",
                "saved_agents": config.get("agents", []),
                "agent": None,
                "status": None
            })
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "api_key": current_config.get("api_key"),
            "error": f"Failed to add agent: {str(e)}",
            "saved_agents": config.get("agents", []),
            "agent": None,
            "status": None
        })

@app.post("/switch/{api_key}")
async def switch_agent(api_key: str):
    config = load_config()
    # verify it exists in our saved agents
    if any(a.get("api_key") == api_key for a in config.get("agents", [])):
        config["active_key"] = api_key
        save_config(config)
        current_config["api_key"] = api_key
    return RedirectResponse(url="/", status_code=303)

@app.post("/delete/{api_key}")
async def delete_agent(api_key: str):
    config = load_config()
    config["agents"] = [a for a in config.get("agents", []) if a.get("api_key") != api_key]
    if config.get("active_key") == api_key:
        config["active_key"] = config["agents"][0].get("api_key") if config["agents"] else None
    save_config(config)
    current_config["api_key"] = config["active_key"]
    return RedirectResponse(url="/", status_code=303)

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register(request: Request, name: str = Form(...), description: str = Form("")):
    try:
        res = requests.post(f"{API_BASE}/agents/register", json={"name": name, "description": description})
        res.raise_for_status()
        data = res.json()
        agent = data.get("agent", {})
        
        # Save and set current
        add_agent_to_config({
            "api_key": agent.get("api_key"),
            "agent_name": name,
            "claim_url": agent.get("claim_url"),
            "verification_code": agent.get("verification_code")
        })
        
        return templates.TemplateResponse("register_success.html", {
            "agent": agent,
            "request": request
        })
    except requests.exceptions.HTTPError as e:
        error_msg = str(e)
        try:
            error_data = e.response.json()
            if error_data.get("error"):
                error_msg = f"{error_data['error']} (Hint: {error_data.get('hint', 'Try a different name')})"
        except:
            pass
        return templates.TemplateResponse("register.html", {"request": request, "error": error_msg})
    except Exception as e:
        return templates.TemplateResponse("register.html", {"request": request, "error": str(e)})


@app.get("/my-post")
async def my_post_redirect():
    return RedirectResponse(url="/my-posts")

@app.get("/my-posts", response_class=HTMLResponse)
async def my_posts(request: Request):
    api_key = current_config.get("api_key")
    if not api_key:
        return RedirectResponse(url="/login")
    
    posts = []
    agent_name = "Unknown"
    s = get_session(api_key)
    try:
        # Fetch agent info which includes recentPosts according to docs
        res = s.get(f"{API_BASE}/agents/me")
        if res.status_code == 200:
            data = res.json()
            agent_name = data.get("agent", {}).get("name", "Unknown")
            posts = data.get("recentPosts", [])
    except Exception as e:
        print(f"Error fetching posts: {e}")

    return templates.TemplateResponse("my_posts.html", {
        "request": request, 
        "posts": posts,
        "agent_name": agent_name
    })

@app.post("/post")
async def create_post(
    request: Request,
    title: str = Form(...), 
    content: Optional[str] = Form(None), 
    url: Optional[str] = Form(None), 
    submolt: str = Form("general")
):
    api_key = current_config.get("api_key")
    if not api_key:
        return RedirectResponse(url="/login")
    
    s = get_session(api_key)
    
    # Pre-fetch submolts for re-rendering if needed
    submolts = []
    try:
        res_subs = s.get(f"{API_BASE}/submolts")
        if res_subs.status_code == 200:
            subs_data = res_subs.json()
            submolts = subs_data.get("submolts") or subs_data.get("data", {}).get("submolts") or []
    except:
        pass

    payload = {"title": title, "submolt": submolt}
    if url:
        payload["url"] = url
    else:
        payload["content"] = content
        
    try:
        res = s.post(f"{API_BASE}/posts", json=payload)
        res.raise_for_status()
        return templates.TemplateResponse("post.html", {
            "request": request, 
            "success": "Post created successfully!",
            "submolts": submolts
        })
    except requests.exceptions.HTTPError as e:
        error_msg = e.response.json().get("error", str(e)) if e.response else str(e)
        return templates.TemplateResponse("post.html", {
            "request": request, 
            "error": error_msg,
            "submolts": submolts
        })

@app.post("/logout")
async def logout():
    config = load_config()
    config["active_key"] = None
    save_config(config)
    current_config["api_key"] = None
    return RedirectResponse(url="/login", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
