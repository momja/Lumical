/**
 * Canvas Controller - Handles collaborative drawing with canvas isolation
 *
 * Each canvas instance is identified by:
 * - Canvas Type: 'drawing' (dashboard) or 'sign' (display)
 * - Canvas ID: Sequential numeric identifier (1, 2, 3, etc.)
 *
 * URLs:
 * - /?canvas_id=1, /?canvas_id=2, etc. → Drawing canvases (dashboard interface)
 * - /sign?canvas_id=1, /sign?canvas_id=2, etc. → Sign canvases (display interface)
 *
 * Data Isolation:
 * - Each canvas type + ID combination has isolated canvas data
 * - WebSocket rooms ensure updates only go to clients on the same canvas
 * - Session context automatically determines the correct canvas
 */

// Get the canvases and contexts
const overlayCanvas = document.getElementById('overlayCanvas');
const drawingCanvas = document.getElementById('drawingCanvas');

// Create a hidden canvas to maintain persistent state
const persistentCanvas = document.createElement('canvas');
persistentCanvas.width = drawingCanvas.width;
persistentCanvas.height = drawingCanvas.height;

// Get contexts - overlay is optional
const overlayCtx = overlayCanvas ? overlayCanvas.getContext('2d') : null;
const drawingCtx = drawingCanvas.getContext('2d');
const persistentCtx = persistentCanvas.getContext('2d');

let canvasUpdated = false;
let canvasDeltas = [];

// Store all received deltas from other clients on this canvas
let receivedDeltas = [];

// Flag to track if we've received the initial canvas state
let initialStateReceived = false;

// WebSocket connection will be initialized inline in templates with proper client_id access
// This file contains only the reusable canvas functionality

// Function to reapply all stored deltas to the canvas
// First try to fetch the server's current state, if that fails use our local deltas
async function buildSharedCanvas() {
    // Only try to get server state if we're in a canvas session and have deltas to apply
    if (receivedDeltas.length > 0 || canvasDeltas.length > 0) {
        try {
            const response = await fetch('/get_full_canvas');
            
            // Check if response is successful and has content
            if (response.ok) {
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
            } else {
                // 404 or other error - this is normal for new canvases
                console.log('No existing canvas state on server (this is normal for new canvases)');
            }
        } catch (error) {
            console.log('No canvas state available from server (this is normal for new canvases)');
        }
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

// Initialize canvases with appropriate defaults
function initializeCanvases() {
    // Check if this is the sign interface (should load default overlay)
    // We can detect this by checking if there's a LED display section
    const isSignInterface = !document.getElementById('ledGrid');
    
    if (!overlayCanvas || !isSignInterface) {
        // No overlay canvas OR this is drawing interface - initialize with default size, no overlay
        if (overlayCanvas) {
            overlayCanvas.width = 800;
            overlayCanvas.height = 600;
            // Clear overlay canvas but don't draw anything on it
            if (overlayCtx) {
                overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
            }
        }
        
        drawingCanvas.width = 800;
        drawingCanvas.height = 600;
        persistentCanvas.width = 800;
        persistentCanvas.height = 600;
        
        // Initialize empty canvases
        drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
        persistentCtx.clearRect(0, 0, persistentCanvas.width, persistentCanvas.height);
        
        // Apply any existing deltas after canvas initialization
        buildSharedCanvas();
        return;
    }
    
    // For sign.html (with overlay and no LED grid), load the default overlay image
    const img = new Image();
    img.onload = () => {
        // Resize canvases to match image dimensions
        overlayCanvas.width = img.width;
        overlayCanvas.height = img.height;
        drawingCanvas.width = img.width;
        drawingCanvas.height = img.height;
        persistentCanvas.width = img.width;
        persistentCanvas.height = img.height;

        if (overlayCtx) {
            overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
            // Draw the image at original size
            overlayCtx.drawImage(img, 0, 0, img.width, img.height);
        }

        // Initialize empty canvases
        drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
        persistentCtx.clearRect(0, 0, persistentCanvas.width, persistentCanvas.height);

        // Apply any existing deltas after canvas initialization
        buildSharedCanvas();
    };

    img.src = "../static/sf_logo_horizontal.svg";
}

// Variables to track mouse state
let isDrawing = false;
let lastX = 0;
let lastY = 0;

// Initialize brush size and color
let brushSize = 10;
let brushColor = '#ff0000';

// Update brush size display
const brushSizeValue = document.getElementById('brushSizeValue');
if (brushSizeValue) {
    brushSizeValue.textContent = brushSize;
}

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

const brushSizeInput = document.getElementById('brushSize');
if (brushSizeInput) {
    brushSizeInput.addEventListener('input', (e) => {
        brushSize = e.target.value;
        const brushSizeValue = document.getElementById('brushSizeValue');
        if (brushSizeValue) {
            brushSizeValue.textContent = brushSize;
        }
    });
}

// Overlay file upload (optional - only if element exists)
const overlayFileInput = document.getElementById('overlayFile');
if (overlayFileInput) {
    overlayFileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (event) => {
            const img = new Image();
            img.onload = () => {
                // Resize canvases to match image dimensions
                if (overlayCanvas && overlayCtx) {
                    overlayCanvas.width = img.width;
                    overlayCanvas.height = img.height;
                    overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
                    // Draw the image at original size
                    overlayCtx.drawImage(img, 0, 0, img.width, img.height);
                }
                
                drawingCanvas.width = img.width;
                drawingCanvas.height = img.height;
                persistentCanvas.width = img.width;
                persistentCanvas.height = img.height;

                // Clear both the drawing canvas and persistent canvas when overlay is loaded
                drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
                persistentCtx.clearRect(0, 0, persistentCanvas.width, persistentCanvas.height);
                
                // Also resize the LED canvas to match if it exists (for drawing.html)
                const ledCanvas = document.getElementById('ledCanvas');
                if (ledCanvas) {
                    ledCanvas.width = img.width;
                    ledCanvas.height = img.height;
                    
                    // Re-initialize the LED canvas with new dimensions
                    if (window.ledManager && typeof window.ledManager.initializeLEDCanvas === 'function') {
                        window.ledManager.initializeLEDCanvas();
                    }
                }
                
                // Reapply all deltas to the new canvas size instead of clearing
                buildSharedCanvas();
            };
            img.src = event.target.result;
        };
        reader.readAsDataURL(file);
    }
    });
}

// Clear canvas function - will be called from template with proper client_id
function clearCanvas(clientId, socket) {
    // Clear both visible and persistent canvases
    drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
    persistentCtx.clearRect(0, 0, persistentCanvas.width, persistentCanvas.height);

    // Clear all stored deltas when explicitly clearing the canvas
    receivedDeltas = [];
    canvasDeltas = [];
    canvasUpdated = true;

    // Send a clear canvas command via WebSocket
    if (socket && clientId) {
        socket.emit('clear_canvas', {
            client_id: clientId,
            timestamp: Date.now()
        });
        console.log('Clear canvas command sent via WebSocket');
    }
}

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

// Function to send canvas data to server - will be called from template with proper client_id and socket
function sendCanvasToServer(clientId, socket) {
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
    if (socket && clientId) {
        mergedDelta.toBlob(blob => {
            // Convert blob to base64 string for WebSocket transmission
            const reader = new FileReader();
            reader.onloadend = function() {
                // Get base64 data (remove the data URL prefix)
                const base64data = reader.result.split(',')[1];

                // Send the delta via WebSocket
                socket.emit('client_delta', {
                    delta_image: base64data,
                    client_id: clientId,
                    timestamp: Date.now(),
                    width: mergedDelta.width,
                    height: mergedDelta.height
                });
                console.log('Delta sent via WebSocket');
            };
            reader.readAsDataURL(blob);
        }, 'image/png');
    }
}

// Function to handle received deltas from other clients
function handleReceivedDelta(data, sessionClientId) {
    // Only apply deltas from other clients, not our own
    if (data.clientId !== sessionClientId) {
        console.log(`Received delta from client ${data.clientId}, applying to canvas`);
        
        // Store the delta for rebuilding the canvas
        receivedDeltas.push({
            deltaImage: data.deltaImage,
            clientId: data.clientId,
            timestamp: data.timestamp
        });
        
        // Apply the delta immediately by layering it on top of existing content
        const img = new Image();
        img.onload = function() {
            // Use composite operation to layer the delta on top
            drawingCtx.globalCompositeOperation = 'source-over';
            drawingCtx.drawImage(img, 0, 0);
            
            persistentCtx.globalCompositeOperation = 'source-over';
            persistentCtx.drawImage(img, 0, 0);
            
            console.log(`Applied delta from client ${data.clientId}`);
        };
        img.src = data.deltaImage;
    } else {
        console.log(`Received delta from own client ${data.clientId}, ignoring`);
    }
}

// Function to handle clear canvas commands
function handleClearCanvas(data) {
    console.log('Received clear canvas command');
    
    // Clear both canvases
    drawingCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
    persistentCtx.clearRect(0, 0, persistentCanvas.width, persistentCanvas.height);
    
    // Clear stored deltas
    receivedDeltas = [];
    canvasDeltas = [];
    
    console.log('Canvas cleared');
}

// Initialize and export functions when DOM is ready
function initializeCanvasController() {
    // Export functions for use in templates
    window.clearCanvasFunction = clearCanvas;
    window.sendCanvasToServerFunction = sendCanvasToServer;
    window.handleReceivedDelta = handleReceivedDelta;
    window.handleClearCanvas = handleClearCanvas;
    
    console.log('Canvas controller functions exported to window');
    
    // Initialize canvases
    initializeCanvases();
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeCanvasController);
} else {
    initializeCanvasController();
}
