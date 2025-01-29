import asyncio
from datetime import datetime, UTC
import logging
import os
from pathlib import Path
from typing import Optional
from uuid import UUID
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from anthropic import AsyncAnthropic
import boto3
from hypercorn.config import Config
from hypercorn.asyncio import serve
from quart import Quart, render_template, request, jsonify, redirect
from sqlmodel import select

from db.engine import db_engine
from db.models import Webpage

logger = logging.getLogger(__name__)
anthropic = AsyncAnthropic()
app = Quart(__name__)
s3_client = boto3.client('s3')
S3_BUCKET = os.environ['AWS_S3_BUCKET']
S3_REGION = s3_client.get_bucket_location(Bucket=S3_BUCKET)['LocationConstraint'] or 'us-east-1'
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


@app.route('/healthcheck')
async def healthcheck():
    return 'okay'


@app.route('/')
@app.route('/<webpage_id>')
async def index(webpage_id=None):
    if webpage_id is None:
        return await render_template('index.html')
    try:
        webpage_uuid = UUID(webpage_id)
    except ValueError:
        return redirect('/')

    async with db_engine.create_session() as session:
        webpage = (await session.execute(
            select(Webpage).where(Webpage.id == webpage_uuid)
        )).scalar()
        if webpage is not None:
            return webpage.html

    return redirect('/')


@app.route('/call_claude', methods=['POST'])
async def call_claude():
    data = await request.get_json()
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
    form = await request.form
    files = await request.files

    html = form.get('html')
    prompt = form.get('prompt')
    parent_id = form.get('parent_id')
    image_files = files.getlist('image_files')

    if not html or not prompt:
        return 'Missing html or prompt', 400

    if parent_id:
        try:
            parent_uuid = UUID(parent_id)
        except ValueError:
            return 'Invalid parent_id format', 400
    else:
        parent_uuid = initial_webpage_id

    file_info = ''
    for file in image_files:
        file_url = upload_file_to_s3(file)
        file_info += f"\nFile '{file.filename}' has been uploaded and is available at: {file_url}"

    try:
        message = await anthropic.messages.create(
            model='claude-3-5-sonnet-20241022',
            max_tokens=4096,
            messages=[{
                'role': 'user',
                'content': f"""You are an expert web developer. Modify the following HTML according to this request: {prompt}

Additional context: {file_info if file_info else 'No files were uploaded'}

IMPORTANT: Do not remove or modify the self-modification card (the section that allows users to modify the webpage) unless explicitly asked to do so in the prompt.

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

Return ONLY the modified HTML. Do not include any explanations or markdown formatting.""" # noqa
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


def upload_file_to_s3(file: FileStorage) -> str:
    now = datetime.now(UTC)
    timestamp = now.strftime('%Y%m%d_%H%M%S_') + f'{int(now.microsecond/1000):03d}'
    filename = f'{timestamp}_{secure_filename(file.filename)}'
    s3_client.upload_fileobj(
        file.stream,
        S3_BUCKET,
        filename,
        ExtraArgs={'ContentType': file.content_type}
    )
    url = f'https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{filename}'
    return url


if __name__ == '__main__':
    hc_config = Config()
    hc_config.bind = ['0.0.0.0:8008']
    hc_config.accesslog = 'iw.log'
    hc_config.errorlog = 'iw.log'
    hc_config.loglevel = 'INFO'
    hc_config.logconfig_dict = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '[%(asctime)s | %(levelname)s | %(name)s] %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S %z'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
                'stream': 'ext://sys.stdout'
            },
            'file': {
                'class': 'logging.FileHandler',
                'formatter': 'standard',
                'filename': 'iw.log',
                'mode': 'a'
            }
        },
        'loggers': {
            'hypercorn.access': {
                'level': 'INFO',
                'handlers': ['console', 'file']
            },
            'hypercorn.error': {
                'level': 'INFO',
                'handlers': ['console', 'file']
            }
        }
    }
    asyncio.run(serve(app, hc_config))
