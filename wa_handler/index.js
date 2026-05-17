/**
 * Sky AI WhatsApp Agent - Baileys WhatsApp Handler
 * Manages WhatsApp Web connection, pairing, messaging via Baileys
 * Communicates with Python parent process via JSON over stdio
 */
import { makeWASocket, useMultiFileAuthState, DisconnectReason, Browsers } from '@whiskeysockets/baileys';
import { Boom } from '@hapi/boom';
import pino from 'pino';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import readline from 'readline';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUTH_DIR = path.join(__dirname, 'auth_info');

// Suppress Baileys debug logs
const logger = pino({ level: 'silent' });

// Ensure auth directory exists
if (!fs.existsSync(AUTH_DIR)) {
    fs.mkdirSync(AUTH_DIR, { recursive: true });
}

// Send structured JSON to stdout (read by Python parent)
function sendToParent(data) {
    try {
        process.stdout.write(JSON.stringify(data) + '\n');
    } catch (e) {
        // stdout closed, ignore
    }
}

// Read commands from parent process via stdin
const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
});

let sock = null;
let isConnected = false;

async function startBot() {
    try {
        const { state, saveCreds, clearAuth } = await useMultiFileAuthState(AUTH_DIR);

        sock = makeWASocket({
            auth: state,
            browser: Browsers.macOS('Desktop'),
            printQRInTerminal: false,
            syncFullHistory: false,
            connectTimeoutMs: 120000,
            keepAliveIntervalMs: 30000,
            markOnlineOnConnect: true,
            defaultQueryTimeoutMs: 60000,
            logger: logger,
            retryRequestDelayMs: 500,
            maxRetries: 10,
            generateHighQualityLinkPreview: false,
            transactionOpts: {
                maxCommitRetries: 10,
                delayBetweenRetriesMs: 500
            },
            linkPreviewImageThumbnailWidth: 192,
            patchMessageBeforeSending: (message) => {
                return message;
            },
            shouldSyncHistoryMessage: () => {
                return false; // Don't sync full history
            }
        });

        // Handle connection updates
        sock.ev.on('connection.update', async (update) => {
            const { connection, lastDisconnect, qr } = update;

            if (qr && !isConnected) {
                sendToParent({ type: 'qr', qr: 'QR received' });
            }

            if (connection === 'open') {
                isConnected = true;
                const user = sock.user;
                sendToParent({
                    type: 'ready',
                    message: 'WhatsApp connected successfully!',
                    user: user ? `${user.id}` : 'Unknown'
                });
            }

            if (connection === 'close') {
                isConnected = false;
                const statusCode = (lastDisconnect?.error instanceof Boom)
                    ? lastDisconnect.error.output?.statusCode
                    : 500;

                const isLoggedOut = statusCode === DisconnectReason.loggedOut;

                sendToParent({
                    type: 'disconnected',
                    message: isLoggedOut ? 'Logged out from WhatsApp' : 'Connection lost',
                    reconnect: !isLoggedOut,
                    loggedOut: isLoggedOut
                });

                if (!isLoggedOut) {
                    // Auto reconnect after 3 seconds
                    setTimeout(() => {
                        sendToParent({ type: 'info', message: 'Attempting reconnection...' });
                        startBot().catch(err => {
                            sendToParent({ type: 'error', message: `Reconnection failed: ${err.message}` });
                        });
                    }, 3000);
                } else {
                    // Clear auth on logout
                    try {
                        fs.rmSync(AUTH_DIR, { recursive: true, force: true });
                    } catch (e) { /* ignore */ }
                    sendToParent({ type: 'error', message: 'Session expired. Please re-pair.' });
                }
            }
        });

        // Handle credentials update
        sock.ev.on('creds.update', saveCreds);

        // Handle incoming messages
        sock.ev.on('messages.upsert', async (msg) => {
            try {
                if (!msg.messages || msg.messages.length === 0) return;

                for (const message of msg.messages) {
                    // Skip if not a regular message or from bot itself
                    if (!message.key || message.key.fromMe) continue;

                    // Skip status broadcasts
                    if (message.key.remoteJid === 'status@broadcast') continue;

                    // Extract text content
                    let text = '';
                    if (message.message?.conversation) {
                        text = message.message.conversation;
                    } else if (message.message?.extendedTextMessage?.text) {
                        text = message.message.extendedTextMessage.text;
                    } else if (message.message?.imageMessage?.caption) {
                        text = message.message.imageMessage.caption;
                    } else if (message.message?.videoMessage?.caption) {
                        text = message.message.videoMessage.caption;
                    } else if (message.message?.documentMessage?.caption) {
                        text = message.message.documentMessage.caption;
                    } else if (message.message?.listResponseMessage?.singleSelectReply?.selectedRowId) {
                        text = message.message.listResponseMessage.singleSelectReply.selectedRowId;
                    } else if (message.message?.buttonsResponseMessage?.selectedButtonId) {
                        text = message.message.buttonsResponseMessage.selectedButtonId;
                    } else {
                        // Skip non-text messages
                        continue;
                    }

                    const from = message.key.remoteJid;
                    const sender = message.key.participant || from;
                    const pushName = message.pushName || 'Unknown';

                    if (text && text.trim()) {
                        sendToParent({
                            type: 'message',
                            from: from,
                            sender: sender,
                            pushName: pushName,
                            text: text.trim(),
                            timestamp: message.messageTimestamp || Math.floor(Date.now() / 1000)
                        });
                    }
                }
            } catch (e) {
                sendToParent({ type: 'error', message: `Message processing error: ${e.message}` });
            }
        });

        // Handle commands from Python parent
        rl.on('line', async (line) => {
            try {
                const command = JSON.parse(line);
                handleCommand(command);
            } catch (err) {
                sendToParent({ type: 'error', message: `Invalid command format: ${err.message}` });
            }
        });

        // Send startup signal
        sendToParent({ type: 'info', message: 'WhatsApp engine initialized. Waiting for commands...' });

    } catch (err) {
        sendToParent({ type: 'error', message: `Startup error: ${err.message}` });
        setTimeout(startBot, 5000);
    }
}

async function handleCommand(command) {
    if (!sock) {
        sendToParent({ type: 'error', message: 'Socket not initialized yet' });
        return;
    }

    try {
        switch (command.type) {

            case 'pairing': {
                if (!command.number) {
                    sendToParent({ type: 'error', message: 'Phone number required for pairing' });
                    return;
                }

                // Clean and format number
                let number = command.number.replace(/[^0-9]/g, '');
                if (number.startsWith('0')) {
                    number = '62' + number.substring(1);
                } else if (!number.startsWith('62')) {
                    number = '62' + number;
                }

                sendToParent({ type: 'info', message: `Requesting pairing code for: ${number}` });

                try {
                    const code = await sock.requestPairingCode(number);
                    sendToParent({ type: 'pairing_code', code: code });
                } catch (pairErr) {
                    sendToParent({ type: 'error', message: `Pairing failed: ${pairErr.message}` });
                }
                break;
            }

            case 'send_message': {
                if (!command.to || !command.text) {
                    sendToParent({ type: 'error', message: 'Recipient (to) and text required' });
                    return;
                }

                // Split long messages into chunks (WhatsApp 64KB limit)
                const maxLen = 4096;
                let text = command.text;

                if (text.length > maxLen) {
                    const chunks = [];
                    for (let i = 0; i < text.length; i += maxLen) {
                        chunks.push(text.substring(i, i + maxLen));
                    }

                    for (let i = 0; i < chunks.length; i++) {
                        const chunkText = chunks.length > 1
                            ? `[${i + 1}/${chunks.length}]\n\n${chunks[i]}`
                            : chunks[i];

                        await sock.sendMessage(command.to, { text: chunkText });
                    }
                    sendToParent({
                        type: 'sent',
                        to: command.to,
                        chunks: chunks.length,
                        status: 'success'
                    });
                } else {
                    await sock.sendMessage(command.to, { text: text });
                    sendToParent({
                        type: 'sent',
                        to: command.to,
                        status: 'success'
                    });
                }
                break;
            }

            case 'send_typing': {
                if (command.to && command.status !== undefined) {
                    await sock.sendPresenceUpdate(
                        command.status ? 'composing' : 'paused',
                        command.to
                    );
                }
                break;
            }

            case 'logout': {
                sendToParent({ type: 'info', message: 'Logging out...' });
                try {
                    await sock.logout();
                    // Clear auth files
                    fs.rmSync(AUTH_DIR, { recursive: true, force: true });
                } catch (e) { /* ignore */ }
                sendToParent({ type: 'info', message: 'Logged out successfully' });
                process.exit(0);
                break;
            }

            case 'ping': {
                sendToParent({ type: 'pong', connected: isConnected });
                break;
            }

            case 'status': {
                sendToParent({
                    type: 'status_report',
                    connected: isConnected,
                    user: sock.user ? sock.user.id : null,
                    authExists: fs.existsSync(AUTH_DIR)
                });
                break;
            }

            default: {
                sendToParent({ type: 'error', message: `Unknown command: ${command.type}` });
            }
        }
    } catch (err) {
        sendToParent({ type: 'error', message: `Command error (${command.type}): ${err.message}` });
    }
}

// Handle graceful exit
process.on('SIGINT', async () => {
    sendToParent({ type: 'info', message: 'Shutting down...' });
    if (sock) {
        try { await sock.logout(); } catch (e) { /* ignore */ }
    }
    process.exit(0);
});

process.on('SIGTERM', async () => {
    if (sock) {
        try { await sock.logout(); } catch (e) { /* ignore */ }
    }
    process.exit(0);
});

// Handle uncaught errors
process.on('uncaughtException', (err) => {
    sendToParent({ type: 'error', message: `Uncaught: ${err.message}` });
});

process.on('unhandledRejection', (err) => {
    sendToParent({ type: 'error', message: `Unhandled rejection: ${err.message}` });
});

// Start
startBot();
