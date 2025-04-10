// server.js
require('dotenv').config(); // Load environment variables from .env file
const express = require('express');
const cors = require('cors');
const { GoogleGenerativeAI, HarmCategory, HarmBlockThreshold } = require('@google/generative-ai');

const app = express();
const port = process.env.PORT || 3000; // Use environment port or default 3000

// --- Configuration ---
const apiKey = process.env.GEMINI_API_KEY;
if (!apiKey) {
    console.error("Error: GEMINI_API_KEY not found in environment variables.");
    process.exit(1); // Exit if API key is missing
}
const genAI = new GoogleGenerativeAI(apiKey);
const model = genAI.getGenerativeModel({ model: "gemini-pro" }); // Or use newer models like "gemini-1.5-flash", etc.

// List of allowed departments (from PDF) - Crucial for the prompt!
const ALLOWED_DEPARTMENTS = [
    "一般外科",
    "婦產部 婦科",
    "婦產部 產科",
    "感染科",
    "乳房外科"
    // Add any other departments strictly identified from the PDF if needed
];

const generationConfig = {
    temperature: 0.5, // Adjust creativity vs. factuality
    topK: 1,
    topP: 1,
    maxOutputTokens: 150, // Limit response length
};

 const safetySettings = [ // Adjust safety settings as needed
    { category: HarmCategory.HARM_CATEGORY_HARASSMENT, threshold: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE },
    { category: HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE },
    { category: HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE },
    { category: HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE },
 ];


// --- Middleware ---
app.use(cors()); // Enable CORS for requests (configure origins for production)
app.use(express.json()); // Parse JSON request bodies

// --- API Endpoint ---
app.post('/api/recommend', async (req, res) => {
    try {
        const userSymptoms = req.body.symptoms;
        if (!userSymptoms) {
            return res.status(400).json({ error: 'Missing "symptoms" in request body' });
        }

        // --- Construct the Prompt ---
        // This is critical for guiding the AI
        const prompt = `你是一個協助判斷掛號科別的AI助理。請根據使用者描述的症狀，從以下允許的科別列表中，推薦最相關的一個科別。
        允許的科別列表：[<span class="math-inline">\{ALLOWED\_DEPARTMENTS\.join\(', '\)\}\]
