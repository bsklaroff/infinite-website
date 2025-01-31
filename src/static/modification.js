const styles = `
    .modify-card {
        position: fixed;
        bottom: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 90%;
        max-width: 800px;
        border: 1px solid #e2e8f0;
        border-radius: 8px 8px 0 0;
        padding: 1rem;
        box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
        background-color: #ffffff;
        transition: transform 0.3s ease-in-out;
        z-index: 100;
    }
    .modify-card.minimized {
        transform: translateX(-50%) translateY(calc(100% - 40px));
    }
    .modify-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: -1rem -1rem 1rem -1rem;
        padding: 0.5rem 1rem;
        background-color: #f8fafc;
        border-bottom: 1px solid #e2e8f0;
        border-radius: 8px 8px 0 0;
        cursor: pointer;
    }
    .modify-card-header h2 {
        margin: 0;
        font-size: 1rem;
    }
    .modify-card .minimize-button {
        background: none;
        border: none;
        cursor: pointer;
        padding: 0.25rem;
        color: #64748b;
    }
    .modify-card .minimize-button:hover {
        color: #334155;
    }
    .modify-card .input-group {
        display: flex;
        gap: 0.5rem;
        margin: 1rem 0;
    }
    .modify-card .button-group {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }
    .modify-card input[type="file"] {
        display: none;
    }
    .modify-card textarea {
        flex: 1;
        padding: 0.5rem;
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        resize: none;
        min-height: 40px;
        max-height: 200px;
        overflow-y: hidden;
        line-height: 1.5;
        font-family: inherit;
        font-size: inherit;
    }
    .modify-card button {
        padding: 0.5rem 1rem;
        background: #3b82f6;
        color: white;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        transition: background-color 0.2s;
    }
    .modify-card button:hover {
        background: #2563eb;
    }
    .modify-card button:disabled {
        background: #cbd5e0;
        cursor: not-allowed;
    }
    .modify-card #updateButton {
        width: 120px;
    }
    .modify-card #uploadButton {
        width: 120px;
    }
    .modify-card .suggestion-message {
        color: #4a5568;
        font-size: 0.9rem;
        margin: 0.5rem 0;
        font-style: italic;
        display: none;
    }
    .modify-loading-overlay {
        display: none;
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        z-index: 1000;
        justify-content: center;
        align-items: center;
    }
    .modify-loading-overlay .spinner {
        width: 50px;
        height: 50px;
        border: 5px solid #f3f3f3;
        border-top: 5px solid #4a5568;
        border-radius: 50%;
        animation: modify-spin 1s linear infinite;
    }
    @keyframes modify-spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
`;

const styleSheet = document.createElement("style");
styleSheet.textContent = styles;
document.head.appendChild(styleSheet);

// Add HTML content
const content = `
    <div class="modify-card" id="modifyCard">
        <div class="modify-card-header" id="cardHeader">
            <h2>Website Editor</h2>
            <button class="minimize-button" id="minimizeButton">▼</button>
        </div>
        <p>Use the prompt below to describe your changes, and optionally add images to upload to the site.</p>
        <p id="suggestionMessage" class="suggestion-message"></p>
        <div class="input-group">
            <textarea id="promptInput" placeholder="Describe how you'd like to modify the website..." rows="1"></textarea>
            <div class="button-group">
                <input type="file" id="imageInput" accept="image/*" multiple onchange="updateFileCount()">
                <button id="uploadButton" onclick="document.getElementById('imageInput').click()">Add Images</button>
                <button id="updateButton" onclick="handleUpdate()">Update</button>
            </div>
        </div>
    </div>
    <div class="modify-loading-overlay" id="loadingOverlay">
        <div class="spinner"></div>
    </div>
`;

document.body.innerHTML += content;


// Initialize elements after content is added
const promptInput = document.getElementById('promptInput');
const updateButton = document.getElementById('updateButton');
const loadingOverlay = document.getElementById('loadingOverlay');
const modifyCard = document.getElementById('modifyCard');
const minimizeButton = document.getElementById('minimizeButton');
const cardHeader = document.getElementById('cardHeader');

let isMinimized = false;

function toggleMinimize() {
    isMinimized = !isMinimized;
    modifyCard.classList.toggle('minimized');
    minimizeButton.textContent = isMinimized ? '▲' : '▼';
}

minimizeButton.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleMinimize();
});

cardHeader.addEventListener('click', () => {
    toggleMinimize();
});

// Focus the prompt input when maximized
cardHeader.addEventListener('click', () => {
    if (isMinimized) {
        setTimeout(() => promptInput.focus(), 300);
    }
});

function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
}

promptInput.addEventListener('input', () => {
    autoResize(promptInput);
});

function prefillEditPrompt(suggestion) {
    const promptInput = document.getElementById('promptInput');
    const suggestionMessage = document.getElementById('suggestionMessage');
    promptInput.value = suggestion;
    suggestionMessage.textContent = "A suggested edit has been prefilled. Feel free to modify it before updating.";
    suggestionMessage.style.display = 'block';
    promptInput.focus();
    promptInput.select();
    autoResize(promptInput);
}

function updateFileCount() {
    const fileCount = document.getElementById('imageInput').files.length;
    const uploadButton = document.getElementById('uploadButton');
    if (fileCount === 0) {
        uploadButton.textContent = 'Add Images';
    } else {
        uploadButton.textContent = `${fileCount} Image${fileCount === 1 ? '' : 's'}`;
    }
}

async function handleUpdate() {
    const prompt = promptInput.value.trim();
    if (!prompt) return;

    const formData = new FormData();
    formData.append('prompt', prompt);
    formData.append('parent_id', window.location.pathname.substring(1));
    Array.from(document.getElementById('imageInput').files).forEach(file => {
        formData.append('image_files', file);
    });

    updateButton.disabled = true;
    loadingOverlay.style.display = 'flex';
    const originalText = updateButton.textContent;
    updateButton.innerHTML = 'Updating...';

    try {
        const response = await fetch('/modify', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Server error: ${errorText}`);
        }

        const id = await response.text();
        window.location.href = `/${id}`;
    } catch (error) {
        console.error('Error:', error);
        updateButton.disabled = false;
        updateButton.innerHTML = originalText;
        loadingOverlay.style.display = 'none';
    }
}

// Add event listener for Enter key
promptInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault(); // Prevent newline
        if (!updateButton.disabled) {
            handleUpdate();
        }
    }
});

promptInput.focus();
autoResize(promptInput);
updateFileCount();
