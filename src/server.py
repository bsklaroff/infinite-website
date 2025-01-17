from anthropic import AsyncAnthropic
import asyncio
from flask import Flask, render_template, request, jsonify, redirect
import logging
import os
from pathlib import Path
from sqlmodel import select, Session
from typing import Optional
from uuid import UUID

from db.engine import db_engine
from db.models import Webpage

logger = logging.getLogger(__name__)
anthropic = AsyncAnthropic()
app = Flask(__name__)
initial_webpage_id: Optional[UUID] = None


async def init_app():
    global initial_webpage_id
    initial_webpage_id = await get_or_create_initial_webpage()
    return app


async def get_or_create_initial_webpage():
    template_path = Path(__file__).parent / 'templates' / 'index.html'
    with open(template_path, 'r') as f:
        template_html = f.read()

    async with db_engine.create_session() as session:
        initial_page = (await session.execute(
            select(Webpage)
            .where(Webpage.html == template_html)
        )).scalar()

        if initial_page is None:
            initial_page = Webpage(html=template_html)
            session.add(initial_page)
            await session.commit()
            await session.refresh(initial_page)

        return initial_page.id


@app.route('/')
@app.route('/<webpage_id>')
async def index(webpage_id=None):
    if webpage_id is None:
        return render_template('index.html')

    async with db_engine.create_session() as session:
        webpage = (await session.execute(select(Webpage).where(Webpage.id == webpage_id))).scalar()
        if webpage is not None:
            return webpage.html

    return redirect('/')


@app.route('/call_claude', methods=['POST'])
async def call_claude():
    data = request.get_json()
    prompt = data.get('prompt')

    if not prompt:
        return 'Missing prompt', 400

    try:
        message = await anthropic.messages.create(
            model='claude-3-5-sonnet-20241022',
            max_tokens=4096,
            messages=[{
                'role': 'user',
                'content': prompt
            }]
        )
        return jsonify({'response': message.content[0].text})

    except Exception as e:
        logger.error(f'Error asking Claude: {str(e)}')
        return str(e), 500


@app.route('/modify', methods=['POST'])
async def modify():
    data = request.get_json()
    html = data.get('html')
    prompt = data.get('prompt')
    parent_id = data.get('parent_id')

    if not html or not prompt:
        return 'Missing html or prompt', 400

    if parent_id:
        try:
            parent_uuid = UUID(parent_id)
        except ValueError:
            return 'Invalid parent_id format', 400
    else:
        parent_uuid = initial_webpage_id

    try:
        message = await anthropic.messages.create(
            model='claude-3-5-sonnet-20241022',
            max_tokens=4096,
            messages=[{
                'role': 'user',
                'content': f"""You are an expert web developer. Modify the following HTML according to this request: {prompt}

You can add direct Claude interaction capabilities to the webpage by implementing JavaScript functions that use the /call_claude endpoint. This endpoint accepts POST requests with a JSON body containing a 'prompt' field and returns Claude's response.

Example usage in JavaScript:
fetch('/call_claude', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ prompt: "user's question" }})
}})
.then(response => response.json())
.then(data => {{
    // data.response contains Claude's message as a string
    console.log('Claude says:', data.response);
}});

Here is the current HTML:
{html}

Return ONLY the modified HTML. Do not include any explanations or markdown formatting."""
            }]
        )
        modified_html = message.content[0].text

        async with db_engine.create_session() as session:
            webpage = Webpage(html=modified_html, parent_id=parent_uuid, prompt=prompt)
            session.add(webpage)
            await session.commit()
            await session.refresh(webpage)
            return str(webpage.id)

    except Exception as e:
        logger.error(f'Error modifying webpage: {str(e)}')
        return str(e), 500
