// static/js/chat.js
let messageHistory = [];

document.addEventListener('DOMContentLoaded', function() {
    messageInput = document.getElementById('messageInput');

    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    }, false);

    var imageInput = document.getElementById('imageInput');
    // Event listener for file input change
    imageInput.addEventListener('change', function(event) {
        var files = event.target.files;
        // TODO: Handle the file upload here
        console.log(files);
    });
    
    var sidebar = document.getElementById('sidebar');
    var chatContainer = document.querySelector('.chat-container');
    document.getElementById('toggleSidebar').addEventListener('click', function() {
        // Toggle the open class on the sidebar
        sidebar.classList.toggle('open');
        
        // Adjust the chat container margin when the sidebar is open
        if (sidebar.classList.contains('open')) {
            chatContainer.classList.add('with-sidebar');
        } else {
            chatContainer.classList.remove('with-sidebar');
        }
    });

    var fileInput = document.getElementById('fileInput');
    var fileDisplayArea = document.getElementById('fileDisplayArea');
    var messageForm = document.getElementById('messageForm');

    // Handle Drag Over the window
    document.addEventListener('dragover', function (e) {
        e.preventDefault();
        e.stopPropagation();
        // You can add some visual feedback here if needed
    });

    // Handle Drop anywhere on the document
    document.addEventListener('drop', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var files = e.dataTransfer.files;
        handleFiles(files);
    });

    // Handle file selection via button
    fileInput.addEventListener('change', function () {
        var files = fileInput.files;
        handleFiles(files);
    });

    function handleFiles(files) {
        // Implement the logic to handle the uploaded files
        console.log(files);
        if (files.length > 0) {
            var file = files[0];
            displayFileInForm(file);
        }
        // You can process the files or send them to the server here
    }

    function displayFileInForm(file) {
        // Clear the previous image
        fileDisplayArea.innerHTML = '';

        // Create an image element
        var imgPreview = document.createElement('img');
        imgPreview.src = URL.createObjectURL(file); // Set the source of the image to the uploaded file
        imgPreview.classList.add('img-preview');
        imgPreview.onload = function() {
            URL.revokeObjectURL(imgPreview.src); // Free memory when the image is loaded
        };
        fileDisplayArea.appendChild(imgPreview);

        // Create remove file icon
        var removeFileIcon = document.createElement('span');
        removeFileIcon.textContent = '❌'; // Example with an emoji
        removeFileIcon.classList.add('remove-file');
        removeFileIcon.onclick = function() {
            // Clear file input
            fileInput.value = '';
            // Hide file display area
            fileDisplayArea.innerHTML = '';
            fileDisplayArea.style.display = 'none';
        };

        // Append remove icon after the image
        fileDisplayArea.appendChild(removeFileIcon);

        // Show file display area
        fileDisplayArea.style.display = 'block';
    }
    var messageInput = document.getElementById('messageInput');
    var messageForm = document.getElementById('messageForm');

    messageInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            var event = new Event('submit', {
                'bubbles': true,
                'cancelable': true
            });
            messageForm.dispatchEvent(event);
        }
    });

    let ws;
    const messageList = document.getElementById("messages");

    function connect() {
        ws = new WebSocket("ws://localhost:10000/ws/generation");
        ws.onopen = () => console.log("Connected to WebSocket");
        ws.onmessage = handleServerMessage;
        ws.onclose = (event) => {
            console.log("Socket closed. Attempting to reconnect...");
            console.log(`Socket closed with code ${event.code}, reason: ${event.reason}`);
            setTimeout(connect, 1000);
        };
        ws.onerror = (event) => {
            console.error("WebSocket error observed:", event);
            ws.close();
        };
    }

    let currentAssistantMessageDiv = null; // Element for ongoing assistant message
    let currentAssistantMessageContent = "";  // Store the ongoing content

    function handleServerMessage(event) {
        const data = JSON.parse(event.data);
        console.log("received: " + data)
        if (data.role === 'assistant' || data.role === undefined) {
            if (data.content !== undefined) {
                currentAssistantMessageContent += data.content.replace(/\n/g, '<br>');// Replace newlines with HTML line breaks;

                if (!currentAssistantMessageDiv) {
                    currentAssistantMessageDiv = document.createElement('div');
                    currentAssistantMessageDiv.classList.add('server-message');
                    messageList.appendChild(currentAssistantMessageDiv);
                }
                currentAssistantMessageDiv.innerHTML = "<b>PetGPT</b>: "+ currentAssistantMessageContent;
            }

            if (data.finished) {
                messageHistory.push({
                    role: 'assistant',
                    content: currentAssistantMessageContent,
                    timestamp: new Date().toISOString()
                });
                currentAssistantMessageDiv = null;
                currentAssistantMessageContent = "";  // Reset the content for the next message
            }
        } else if (data.role === 'user') {
            appendMessage(data.content, data.role);
        }

        messageList.scrollTop = messageList.scrollHeight;
    }
    
    function appendMessage(content, role) {
        if (role === 'user' && content !== undefined) {
            const messageDiv = document.createElement('div');
            messageDiv.classList.add('user-message');
            messageDiv.innerHTML = `<b>You</b>: ${content}`;
            messageList.appendChild(messageDiv);
    
            messageHistory.push({
                role: role,
                content: content,
                timestamp: new Date().toISOString()
            });
        }
    }

    function sendMessage(message, role) {
        
        appendMessage(message, role); // Add message to UI and history

        // Construct and send the payload
        const data = JSON.stringify({ messages: messageHistory });
        if (ws.readyState === WebSocket.OPEN) {
            console.log("sendMessage: " + data);
            ws.send(data);
        } else {
            console.log("WebSocket is not open. Attempting to reconnect before sending.");
            connect();
        }
    }

    document.getElementById("messageForm").addEventListener("submit", (event) => {
        event.preventDefault();
        const inputElement = document.getElementById("messageInput");
        const message = inputElement.value.trim();
        if (message) {
            sendMessage(message, 'user');
            inputElement.value = ""; // Clear input field after sending
        }
    });

    connect(); // Initial connection
});

function processPetInfo(petName, petImages) {
    // Convert FileList to Array
    const imagesArray = Array.from(petImages);

    // Display images in the imageContainer
    const imageContainer = document.getElementById('imageContainer');
    imageContainer.innerHTML = ''; // Clear any existing content
    imagesArray.forEach(image => {
        const imgElement = document.createElement('img');
        imgElement.src = URL.createObjectURL(image);
        imgElement.style.maxWidth = '100px'; // Set a max width for the image
        imgElement.style.marginRight = '10px'; // Add some margin between images
        imageContainer.appendChild(imgElement);
    });

    convertImagesToBase64(imagesArray).then(base64Images => {
        const payload = {
            petName: petName,
            petImages: base64Images
        };

    });
}

function convertImagesToBase64(images) {
    const promises = images.map(image => {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(image);
        });
    });
    return Promise.all(promises);
}

function handleFileUpload(event) {
    const [file] = event.target.files;
    const preview = document.getElementById("imagePreview");
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            preview.innerHTML = `<img src="${e.target.result}" style="max-width: 100px; max-height: 100px;" />`; // Adjust size as needed
        };
        reader.readAsDataURL(file);
    }
}