import asyncio
from datetime import datetime, UTC
import logging
import os
from pathlib import Path
import re
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
anthropic = AsyncAnthropic(api_key=os.environ['IW_ANTHROPIC_API_KEY'])
app = Quart(__name__)
s3_client = boto3.client('s3')
S3_BUCKET = os.environ['AWS_S3_BUCKET']
S3_REGION = s3_client.get_bucket_location(Bucket=S3_BUCKET)['LocationConstraint'] or 'us-east-1'


@app.before_serving
async def init_app() -> None:
    """Use the template to get the initial_webpage_id from the DB, or insert it if not found"""
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

        app.config['INITIAL_WEBPAGE_ID'] = initial_page.id


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

    prompt = form.get('prompt')
    parent_id = form.get('parent_id')
    image_files = files.getlist('image_files')

    if not prompt:
        return 'Missing prompt', 400

    try:
        parent_uuid = UUID(parent_id) if parent_id else app.config['INITIAL_WEBPAGE_ID']
    except ValueError:
        return 'Invalid parent_id format', 400

    async with db_engine.create_session() as session:
        parent_webpage = (await session.execute(
            select(Webpage).where(Webpage.id == parent_uuid)
        )).scalar()
        if parent_webpage is None:
            return 'Parent webpage not found', 400
        html = parent_webpage.html

    file_info = ''
    for file in image_files:
        file_url = upload_file_to_s3(file)
        file_info += f"\nFile '{file.filename}' has been uploaded and is available at: {file_url}"

    try:
        # SEARCH/REPLACE instructions copied from https://github.com/Aider-AI/aider
        message = await anthropic.messages.create(
            model='claude-3-5-sonnet-20241022',
            max_tokens=4096,
            messages=[{
                'role': 'user',
                'content': f"""You are an expert web developer.
You are diligent and tireless!
You NEVER leave comments describing code without implementing it!
You always COMPLETELY IMPLEMENT the needed code!

Given the user's modification request, take the following steps:

1. Think step-by-step and explain the needed changes in a few short sentences.
2. Describe each change with a *SEARCH/REPLACE block* per the instructions below:

All changes to the source must use the following *SEARCH/REPLACE block* format.
Describe each change with a *SEARCH/REPLACE block*.
ONLY EVER RETURN CODE IN A *SEARCH/REPLACE BLOCK*!

Every *SEARCH/REPLACE block* must use this format:
1. The start of search block: <<<<<<< SEARCH
2. A contiguous chunk of lines to search for in the existing source code
3. The dividing line: =======
4. The lines to replace into the source code
5. The end of the replace block: >>>>>>> REPLACE

Every *SEARCH* section must *EXACTLY MATCH* the existing source content, character for character, including all indentation, comments, docstrings, etc.
If the source contains code or other data wrapped/escaped in json/xml/quotes or other containers, you need to propose edits to the literal contents of the file, including the container markup.

Keep *SEARCH/REPLACE* blocks concise.
Break large *SEARCH/REPLACE* blocks into a series of smaller blocks that each change a small portion of the source.
Include just the changing lines, and a few surrounding lines if needed for uniqueness.
Do not include long runs of unchanging lines in *SEARCH/REPLACE* blocks.

*SEARCH/REPLACE* blocks will *only* replace the first match occurrence.
Including multiple unique *SEARCH/REPLACE* blocks if needed.
Include enough lines in each SEARCH section to uniquely match each set of lines that need to change.

To move code within the source HTML, use 2 *SEARCH/REPLACE* blocks: 1 to delete it from its current location, 1 to insert it in the new location.

For client-side routing, you can create new pages by:
1. Adding HTML div elements with id="pageName" class="page" at the top-level of the body of the html
2. Using the Router class to register routes with router.addRoute('pageName', callback)
3. Linking to pages with href="#pageName"

Only add new pages if there are multiple separate pages worth of information to display (the self-modification card does not count, and should stay at the bottom of all pages unless otherwise specified by the user).

You can add direct Claude interaction capabilities to the webpage by implementing JavaScript functions that use the /call_claude endpoint. This endpoint accepts POST requests with a JSON body containing a 'prompt' field and returns Claude's response.

Example Claude interaction in JavaScript:
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

Additional context for newly uploaded files: {file_info if file_info else 'No files were uploaded'}

IMPORTANT: Do not remove the self-modification card (the section that allows users to modify the webpage) unless explicitly asked to do so in the prompt.

Modify the following HTML source according to this request: {prompt}

Here is the source HTML:
{html}

Please try to make the resulting website look as professional as possible.
You are diligent and tireless!
You NEVER leave comments describing code without implementing it!
You always COMPLETELY IMPLEMENT the needed code!
ONLY EVER RETURN CODE IN A *SEARCH/REPLACE BLOCK*!""" # noqa
            }]
        )
        llm_response = message.content[0].text
        modified_html = apply_search_replace_blocks(html, llm_response)

        async with db_engine.create_session() as session:
            webpage = Webpage(
                html=modified_html,
                parent_id=parent_uuid,
                prompt=prompt,
                llm_response=llm_response,
            )
            session.add(webpage)
            await session.commit()
            await session.refresh(webpage)
            return str(webpage.id)

    except Exception as e:
        logger.error(f'Error modifying webpage: {str(e)}')
        return str(e), 500


def apply_search_replace_blocks(html: str, blocks_text: str) -> str:
    pattern = r'<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE'
    matches = re.finditer(pattern, blocks_text, re.DOTALL)
    blocks = [(m.group(1), m.group(2)) for m in matches]
    modified = html
    for search, replace in blocks:
        modified = modified.replace(search, replace, 1)
    return modified


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
            '': {  # Root logger
                'level': 'INFO',
                'handlers': ['console', 'file']
            },
            'hypercorn.access': {
                'level': 'INFO',
                'handlers': ['console', 'file'],
                'propagate': False
            },
            'hypercorn.error': {
                'level': 'INFO',
                'handlers': ['console', 'file'],
                'propagate': False
            }
        }
    }
    asyncio.run(serve(app, hc_config))
