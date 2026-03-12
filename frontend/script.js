// Wait for DOM to load
document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const chatForm = document.getElementById('chatForm');
    const messageInput = document.getElementById('messageInput');
    const chatMessages = document.getElementById('chatMessages');
    const sendBtn = document.getElementById('sendBtn');
    const userIdInput = document.getElementById('userIdInput');
    const trainBtn = document.getElementById('trainBtn');
    const trainStatus = document.getElementById('trainStatus');
    const trainStatusText = document.getElementById('trainStatusText');
    const clearBtn = document.getElementById('clearBtn');

    // Conversation history to pass to context
    let conversationHistory = [];

    // Initialize Markdown and HighlightJS
    marked.setOptions({
        highlight: function(code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                return hljs.highlight(code, { language: lang }).value;
            }
            return hljs.highlightAuto(code).value;
        },
        breaks: true
    });

    // Handle Form Submit (Chat)
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const message = messageInput.value.trim();
        if (!message) return;

        // 1. Add User Message to UI
        appendMessage('user', message);
        messageInput.value = '';
        messageInput.focus();

        // Prevent multiple submissions
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';

        // 2. Add empty bot message container for streaming effect
        const botMsgContainer = appendEmptymessage('support');
        
        try {
            // Check if server uses standard JSON response or SSE Stream. 
            // In app/main.py, /chat is regular POST. Let's use /chat.
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: message,
                    user_id: userIdInput.value.trim() || 'user_123',
                    conversation_history: conversationHistory
                })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.message || 'Server responded with an error');
            }

            const data = await response.json();
            
            // 3. Render bot response with Markdown
            botMsgContainer.innerHTML = marked.parse(data.response);
            
            // Re-apply highlight JS to new blocks
            botMsgContainer.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });

            // Update local history array
            conversationHistory.push({ role: 'user', content: message });
            conversationHistory.push({ role: 'assistant', content: data.response });

            // Optional: Tag Intent if returned
            if (data.intent && data.intent !== 'general') {
                const intentTag = document.createElement('div');
                intentTag.style.fontSize = '0.75rem';
                intentTag.style.color = 'var(--primary)';
                intentTag.style.marginTop = '10px';
                intentTag.style.textAlign = 'right';
                intentTag.innerHTML = `<i class="fa-solid fa-tag"></i> Intent: ${data.intent}`;
                botMsgContainer.appendChild(intentTag);
            }

        } catch (error) {
            console.error(error);
            botMsgContainer.innerHTML = `<span style="color: #ef4444;"><i class="fa-solid fa-triangle-exclamation"></i> Lỗi kết nối: ${error.message}. Xin vui lòng thử lại sau.</span>`;
        } finally {
            // Re-enable send button
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<i class="fa-solid fa-paper-plane"></i>';
            scrollToBottom();
        }
    });

    // Handle Training Button
    trainBtn.addEventListener('click', async () => {
        // UI Feedback
        trainBtn.disabled = true;
        trainBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Training...';
        trainStatus.classList.remove('hidden');
        trainStatusText.innerText = "Kích hoạt Local Training...";
        trainStatus.querySelector('.spinner').style.display = 'block';

        try {
            trainStatusText.innerText = "Đang xây dựng mô hình ONNX. Quá trình này có thể tốn 1-2 phút...";
            
            const response = await fetch('/train/intent', {
                method: 'POST'
            });

            const data = await response.json();

            if (response.ok) {
                trainStatusText.innerText = "🚀 Training Thành Công! Đã thay thế Model.";
                trainStatusText.style.color = "var(--primary)";
                trainStatus.querySelector('.spinner').style.display = 'none';
                console.log(data);
            } else {
                throw new Error(data.detail || 'Training Failed');
            }

        } catch (error) {
            trainStatusText.innerText = `❌ Lỗi: ${error.message}`;
            trainStatusText.style.color = "#ef4444";
            trainStatus.querySelector('.spinner').style.display = 'none';
        } finally {
            trainBtn.disabled = false;
            trainBtn.innerHTML = '<i class="fa-solid fa-brain"></i> Train Local Intent Model';
            
            // Hide status after 5 seconds
            setTimeout(() => {
                trainStatus.classList.add('hidden');
                trainStatusText.style.color = "var(--primary)";
            }, 8000);
        }
    });

    // Handle Clear Button
    clearBtn.addEventListener('click', () => {
        // Remove all messages except the first welcome message
        while (chatMessages.childNodes.length > 3) {
            chatMessages.removeChild(chatMessages.lastChild);
        }
        conversationHistory = [];
    });

    // Helper: Append Message HTML
    function appendMessage(role, text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;
        
        const avatarIcon = role === 'user' ? '<i class="fa-solid fa-user"></i>' : '<i class="fa-solid fa-leaf"></i>';
        
        msgDiv.innerHTML = `
            <div class="avatar">${avatarIcon}</div>
            <div class="message-content">${text}</div>
        `;
        
        chatMessages.appendChild(msgDiv);
        scrollToBottom();
    }

    // Helper: Append Empty Container for Bot (Loading phase)
    function appendEmptymessage(role) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;
        
        const avatarIcon = role === 'user' ? '<i class="fa-solid fa-user"></i>' : '<i class="fa-solid fa-leaf"></i>';
        
        msgDiv.innerHTML = `
            <div class="avatar">${avatarIcon}</div>
            <div class="message-content typing-indicator">
                <i class="fa-solid fa-ellipsis fa-fade"></i> AI đang suy nghĩ...
            </div>
        `;
        
        chatMessages.appendChild(msgDiv);
        scrollToBottom();
        return msgDiv.querySelector('.message-content');
    }

    // Helper: Scroll to bottom
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
});
