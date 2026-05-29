# 👶 Pediatric Board MCQ Study Companion

A premium, interactive desktop web application built in Python using **Streamlit** and integrated with the **Google Gemini API** to help residents, fellows, and medical students study pediatric board MCQs systematically.

This application is fully grounded in textbook chapters that you upload. Gemini automatically extracts a logical progression of study sub-topics and synthesizes high-yield board-style clinical vignettes with detailed diagnostic and treatment explanations.

---

## ✨ Features

- **📂 Multi-PDF Chapter Ingestion**: Upload one or multiple textbook PDFs containing the pediatric chapters or practice questions you wish to study.
- **🧠 Automated Sub-Topic Extraction**: Gemini analyzes the uploaded chapter structures to map out a clear chronological study track of 5 to 10 subtopics.
- **📚 Dynamic MCQ Synthesis**: Generates 10 to 15 high-yield clinical vignettes for each sub-topic, labeled A to E, using standard pediatric board style with realistic distractors.
- **💾 Real-Time Auto-Resume Progress Saving**: Your progress (extracted topics, generated questions, selected answers, and question index) is saved locally in `progress.json` in real time. **You can close your browser or restart the app and instantly pick up right where you left off!**
- **🎨 Premium Slate-Dark Clinical Theme**: Uses a custom-designed clinical aesthetic utilizing clean glassmorphism, responsive styled question cards, micro-animations, and colored explanation alerts.
- **📊 Interactive Timeline & Leaderboard Stepper**: A vertical progression timeline in the sidebar keeps track of your topic status (Completed `✅`, Active `🟢`, Locked `🔒`). Jump directly to any completed or active topic!
- **🏆 Board Readiness Assessment**: Detailed results breakdown at the end of the chapter evaluates your performance and assigns a Board Readiness rating (Developing, Proficient, or Excellent).

---

## 🚀 Setup & Execution

Since the app automatically installs Python 3.12 and sets up a virtual environment, launching is straightforward!

### 1. Launch the Streamlit App

From your terminal in the `Pediatric-MCQ-App` directory, activate the virtual environment and run the Streamlit server:

```powershell
# 1. Activate Virtual Environment
.venv\Scripts\Activate.ps1

# 2. Start the Streamlit Application
streamlit run app.py
```

Streamlit will automatically launch in your default web browser at `http://localhost:8501`.

---

## 📖 How to Use the App

1. **Secure your Gemini API Key**:
   - Go to [Google AI Studio](https://aistudio.google.com/).
   - Click **Create API Key**.
   - Copy the key and paste it securely into the **Gemini API Key** field in the sidebar.
2. **Configure your session**:
   - Select the number of MCQs you want per subtopic (10 to 15 questions).
   - Drag and drop one or more pediatric textbook chapter PDFs in the **Upload Chapter PDF(s)** section.
3. **Analyze and Map**:
   - Click **Process Chapter PDFs**. Gemini will extract and index the text, create a sequential study layout, and render it in the sidebar.
4. **Study Sequentially**:
   - Click **Generate High-Yield Board Questions** to fetch the custom-synthesized questions for the first topic.
   - Choose your answer from A to E, and click **Check Answer ✔️**.
   - Read the **High-Yield Board Pearl** card to learn why the option is correct and review critical conceptual pearls.
   - Use the navigation buttons (**Next Question ➡️**, **⬅️ Previous Question**) to move through the questions.
   - Complete the questions and click **🎉 Complete Topic & Advance!** to move the progress bar forward.
5. **View Board Readiness**:
   - At the end of the chapter, see your overall stats (Total Questions, Questions Correct, Score Percentage) and your board-readiness evaluation.
