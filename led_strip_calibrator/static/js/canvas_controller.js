// Get the canvases and contexts
const overlayCanvas = document.getElementById('overlayCanvas');
const drawingCanvas = document.getElementById('drawingCanvas');

// Create a hidden canvas to maintain persistent state
const persistentCanvas = document.createElement('canvas');
persistentCanvas.width = drawingCanvas.width;
persistentCanvas.height = drawingCanvas.height;

const overlayCtx = overlayCanvas.getContext('2d');
const drawingCtx = drawingCanvas.getContext('2d');
const persistentCtx = persistentCanvas.getContext('2d');

let canvasUpdated = false;
let canvasDeltas = [];

// Store all received deltas from other clients
let receivedDeltas = [];

// Flag to track if we've received the initial canvas state
let initialStateReceived = false;

const socket = io();

socket.on('connect', function() {
    console.log('Connected to the server');
    // We'll receive the initial canvas state via the init_canvas event
});

// Handle initial canvas state from server
socket.on('init_canvas', function(data) {
    console.log('Received initial canvas state from server');

    if (data.success && data.fullStateImage) {
        initialStateReceived = true;

        // Apply the full state to both canvases
        const img = new Image();
        img.onload = function() {
            // Clear both canvases first
            drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
            persistentCtx.clearRect(0, 0, persistentCanvas.width, persistentCanvas.height);

            // Apply the full state
            drawingCtx.drawImage(img, 0, 0);
            persistentCtx.drawImage(img, 0, 0);
            console.log('Applied initial canvas state');
        };
        img.src = data.fullStateImage;
    }
});

// Handle updates from other clients
socket.on('update', function(data) {
    console.log('Received update from server', data);

    // Only process updates from other clients
    const sessionClientId = "{{ session['client_id'] }}";
    if (data.client_id !== sessionClientId) {
        console.log(`Received update from client ${data.client_id}`);

        // Handle canvas clear command
        if (data.clear) {
            console.log('Received canvas clear command');
            drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
            persistentCtx.clearRect(0, 0, persistentCanvas.width, persistentCanvas.height);
            receivedDeltas = [];
            return;
        }

        // If we have a full state image, use that instead of incremental deltas
        if (data.fullStateImage) {
            const fullImg = new Image();
            fullImg.onload = function() {
                // Apply the full state directly
                drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
                persistentCtx.clearRect(0, 0, persistentCanvas.width, persistentCanvas.height);
                drawingCtx.drawImage(fullImg, 0, 0);
                persistentCtx.drawImage(fullImg, 0, 0);
                console.log(`Applied full state from client ${data.client_id}`);
            };
            fullImg.src = data.fullStateImage;
            return;
        }

        // Fall back to delta if no full state is available
        if (data.deltaImage) {
            // Store the delta in our history
            receivedDeltas.push({
                clientId: data.client_id,
                deltaImage: data.deltaImage,
                timestamp: data.timestamp || Date.now()
            });

            // Apply the delta to both our drawing canvas and persistent canvas
            const img = new Image();
            img.onload = function() {
                drawingCtx.drawImage(img, 0, 0);
                persistentCtx.drawImage(img, 0, 0);
                console.log(`Applied delta from client ${data.client_id}`);
            };
            img.src = data.deltaImage;
        }
    }
});

// Add handlers for WebSocket confirmation events
socket.on('delta_received', function(data) {
    console.log('Server confirmed delta received:', data);
});

socket.on('clear_received', function(data) {
    console.log('Server confirmed clear received:', data);
});

// Function to reapply all stored deltas to the canvas
// First try to fetch the server's current state, if that fails use our local deltas
async function buildSharedCanvas() {
    // Try to get the server's complete state first
    try {
        const response = await fetch('/get_full_canvas');
        const data = await response.json();

        if (data.success && data.fullStateImage) {
            // Apply the full state from server
            return new Promise(resolve => {
                const img = new Image();
                img.onload = function() {
                    // Clear both canvases first
                    drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
                    persistentCtx.clearRect(0, 0, persistentCanvas.width, persistentCanvas.height);

                    // Apply the full state
                    drawingCtx.drawImage(img, 0, 0);
                    persistentCtx.drawImage(img, 0, 0);
                    console.log('Applied full canvas state from server');
                    resolve();
                };
                img.src = data.fullStateImage;
            });
        }
    } catch (error) {
        console.log('Failed to get server canvas state, falling back to local deltas', error);
    }

    // If server state fetch failed or returned no data, fall back to local deltas
    // Clear both canvases first
    drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
    persistentCtx.clearRect(0, 0, persistentCanvas.width, persistentCanvas.height);

    // Sort deltas by timestamp to ensure they're applied in the correct order
    receivedDeltas.sort((a, b) => a.timestamp - b.timestamp);

    // We need to load images synchronously to ensure correct layering
    const applyDeltasSequentially = async () => {
        // Apply each remote delta sequentially to both canvases
        for (let i = 0; i < receivedDeltas.length; i++) {
            const delta = receivedDeltas[i];
            await new Promise(resolve => {
                const img = new Image();
                img.onload = function() {
                    drawingCtx.drawImage(img, 0, 0);
                    persistentCtx.drawImage(img, 0, 0);
                    console.log(`Reapplied delta ${i + 1}/${receivedDeltas.length} from client ${delta.clientId}`);
                    resolve();
                };
                img.src = delta.deltaImage;
            });
        }

        // Then apply any pending local deltas
        for (const delta of canvasDeltas) {
            drawingCtx.drawImage(delta.deltaCanvas, 0, 0);
            persistentCtx.drawImage(delta.deltaCanvas, 0, 0);
        }
    };

    return applyDeltasSequentially();
}

// Load default overlay image on page load
function loadDefaultOverlay() {
    const img = new Image();
    img.onload = () => {
        // Resize canvases to match image dimensions
        overlayCanvas.width = img.width;
        overlayCanvas.height = img.height;
        drawingCanvas.width = img.width;
        drawingCanvas.height = img.height;
        persistentCanvas.width = img.width;
        persistentCanvas.height = img.height;

        overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
        // Draw the image at original size
        overlayCtx.drawImage(img, 0, 0, img.width, img.height);

        // Initialize empty canvases
        drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
        persistentCtx.clearRect(0, 0, persistentCanvas.width, persistentCanvas.height);

        // Apply any existing deltas after canvas initialization
        buildSharedCanvas();
    };

    img.src = "static/sf_logo_horizontal.svg";
}

// Variables to track mouse state
let isDrawing = false;
let lastX = 0;
let lastY = 0;

// Initialize brush size and color
let brushSize = 10;
let brushColor = '#ff0000';

// Update brush size display
document.getElementById('brushSizeValue').textContent = brushSize;

// Event listeners for color palette
document.querySelectorAll('.color-swatch').forEach(swatch => {
    swatch.addEventListener('click', (e) => {
        // Remove selected class from all swatches
        document.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('selected'));
        // Add selected class to clicked swatch
        e.target.classList.add('selected');
        // Update brush color
        brushColor = e.target.dataset.color;
    });
});

document.getElementById('brushSize').addEventListener('input', (e) => {
    brushSize = e.target.value;
    document.getElementById('brushSizeValue').textContent = brushSize;
});

// Overlay file upload
document.getElementById('overlayFile').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (event) => {
            const img = new Image();
            img.onload = () => {
                // Resize canvases to match image dimensions
                overlayCanvas.width = img.width;
                overlayCanvas.height = img.height;
                drawingCanvas.width = img.width;
                drawingCanvas.height = img.height;
                persistentCanvas.width = img.width;
                persistentCanvas.height = img.height;

                overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
                // Draw the image at original size
                overlayCtx.drawImage(img, 0, 0, img.width, img.height);

                // Clear both the drawing canvas and persistent canvas when overlay is loaded
                drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
                persistentCtx.clearRect(0, 0, persistentCanvas.width, persistentCanvas.height);
                // Reapply all deltas to the new canvas size instead of clearing

                buildSharedCanvas();
            };
            img.src = event.target.result;
        };
        reader.readAsDataURL(file);
    }
});

// Clear canvas button
document.getElementById('clearCanvas').addEventListener('click', () => {
    // Clear both visible and persistent canvases
    drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
    persistentCtx.clearRect(0, 0, persistentCanvas.width, persistentCanvas.height);

    // Clear all stored deltas when explicitly clearing the canvas
    receivedDeltas = [];
    canvasDeltas = [];
    canvasUpdated = true;

    // Send a clear canvas command via WebSocket
    socket.emit('clear_canvas', {
        client_id: "{{ session['client_id'] }}",
        timestamp: Date.now()
    });
    console.log('Clear canvas command sent via WebSocket');
});

// Drawing functions
function startDrawing(e) {
    isDrawing = true;
    [lastX, lastY] = getMousePos(drawingCanvas, e);
    draw(e); // Draw a dot when clicked
}

function stopDrawing() {
    isDrawing = false;
}

function draw(e) {
    if (!isDrawing) return;

    const [x, y] = getMousePos(drawingCanvas, e);

    // Create a temporary canvas for the delta
    const deltaCanvas = document.createElement('canvas');
    deltaCanvas.width = drawingCanvas.width;
    deltaCanvas.height = drawingCanvas.height;
    const deltaCtx = deltaCanvas.getContext('2d');

    // Draw only the new stroke on the delta canvas
    deltaCtx.lineWidth = brushSize;
    deltaCtx.lineCap = 'round';
    deltaCtx.strokeStyle = brushColor;
    deltaCtx.beginPath();
    deltaCtx.moveTo(lastX, lastY);
    deltaCtx.lineTo(x, y);
    deltaCtx.stroke();

    // Draw on the persistent canvas (our state storage)
    persistentCtx.lineWidth = brushSize;
    persistentCtx.lineCap = 'round';
    persistentCtx.strokeStyle = brushColor;
    persistentCtx.beginPath();
    persistentCtx.moveTo(lastX, lastY);
    persistentCtx.lineTo(x, y);
    persistentCtx.stroke();

    // Also draw on the main canvas (for immediate visual feedback)
    drawingCtx.lineWidth = brushSize;
    drawingCtx.lineCap = 'round';
    drawingCtx.strokeStyle = brushColor;
    drawingCtx.beginPath();
    drawingCtx.moveTo(lastX, lastY);
    drawingCtx.lineTo(x, y);
    drawingCtx.stroke();

    [lastX, lastY] = [x, y];

    // Store the delta for sending
    canvasDeltas.push({
        deltaCanvas: deltaCanvas,
        timestamp: Date.now()
    });
    canvasUpdated = true;
}

// Helper function to get correct mouse position
function getMousePos(canvas, e) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return [
        (e.clientX - rect.left) * scaleX,
        (e.clientY - rect.top) * scaleY
    ];
}

// Event listeners for drawing
drawingCanvas.addEventListener('mousedown', startDrawing);
drawingCanvas.addEventListener('mousemove', draw);
drawingCanvas.addEventListener('mouseup', stopDrawing);
drawingCanvas.addEventListener('mouseout', stopDrawing);

// Touch support for mobile devices
drawingCanvas.addEventListener('touchstart', (e) => {
    e.preventDefault();
    const touch = e.touches[0];
    const mouseEvent = new MouseEvent('mousedown', {
        clientX: touch.clientX,
        clientY: touch.clientY
    });
    drawingCanvas.dispatchEvent(mouseEvent);
});

drawingCanvas.addEventListener('touchmove', (e) => {
    e.preventDefault();
    const touch = e.touches[0];
    const mouseEvent = new MouseEvent('mousemove', {
        clientX: touch.clientX,
        clientY: touch.clientY
    });
    drawingCanvas.dispatchEvent(mouseEvent);
});

drawingCanvas.addEventListener('touchend', (e) => {
    e.preventDefault();
    const mouseEvent = new MouseEvent('mouseup', {});
    drawingCanvas.dispatchEvent(mouseEvent);
});

// Function to create composite canvas for server
function createCompositeCanvas() {
    const compositeCanvas = document.createElement('canvas');
    compositeCanvas.width = drawingCanvas.width;
    compositeCanvas.height = drawingCanvas.height;
    const compositeCtx = compositeCanvas.getContext('2d');

    // Fill with black background first
    compositeCtx.fillStyle = '#000000';
    compositeCtx.fillRect(0, 0, compositeCanvas.width, compositeCanvas.height);

    // Draw drawing layer from the persistent canvas (which has the full state)
    compositeCtx.globalAlpha = 1.0;
    compositeCtx.drawImage(persistentCanvas, 0, 0);

    // Draw overlay with fixed opacity, stretched to fill canvas
    compositeCtx.globalAlpha = 0.8;
    compositeCtx.drawImage(overlayCanvas, 0, 0, compositeCanvas.width, compositeCanvas.height);

    return compositeCanvas;
}

// Function to send canvas data to server
function sendCanvasToServer() {
    // if there have been zero changes to the canvas, do not send to server
    if (!canvasUpdated || canvasDeltas.length === 0) {
        return;
    }

    // Reset canvas changed state
    canvasUpdated = false;

    // Merge all deltas into a single delta canvas
    const mergedDelta = document.createElement('canvas');
    mergedDelta.width = drawingCanvas.width;
    mergedDelta.height = drawingCanvas.height;
    const mergedCtx = mergedDelta.getContext('2d');

    // Apply all deltas to the merged canvas - this is what gets sent to the server
    canvasDeltas.forEach(delta => {
        mergedCtx.drawImage(delta.deltaCanvas, 0, 0);
    });

    // Clear the deltas array
    canvasDeltas = [];

    // Send the merged delta via WebSocket instead of HTTP
    mergedDelta.toBlob(blob => {
        // Convert blob to base64 string for WebSocket transmission
        const reader = new FileReader();
        reader.onloadend = function() {
            // Get base64 data (remove the data URL prefix)
            const base64data = reader.result.split(',')[1];

            // Send the delta via WebSocket
            socket.emit('client_delta', {
                delta_image: base64data,
                client_id: "{{ session['client_id'] }}",
                timestamp: Date.now(),
                width: mergedDelta.width,
                height: mergedDelta.height
            });
            console.log('Delta sent via WebSocket');
        };
        reader.readAsDataURL(blob);
    }, 'image/png');
}

// Send canvas updates more frequently now that we're using WebSockets
setInterval(sendCanvasToServer, 50);

// Initialize connection when page loads
window.addEventListener('DOMContentLoaded', function() {
    console.log('Page loaded, client ID:', "{{ session['client_id'] }}");
});

// Load default overlay when page loads
window.addEventListener('load', loadDefaultOverlay);
