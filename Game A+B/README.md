# 🕵️ AI Lie Detection Game

An interactive AI-powered game built with Python, Gradio, and the OpenAI API. The project explores how AI can be used to create conversational games involving deception, reasoning, and judgment.

## 🎮 Game Modes

### Game A: Can You Spot the AI's Lie?

Players are presented with several statements and must identify which one is false.

- Choose a topic, such as animals.
- Select a difficulty level: Easy, Normal, or Hard.
- Start the game and read the generated statements.
- Select the statement you believe is false.
- Submit your answer and check the result.

### Game B: Can You Fool the AI?

Players attempt to deceive the AI through their answers, while the AI analyzes the responses and makes a judgment.

- Respond to the AI's question or prompt.
- Choose whether to tell the truth or lie, depending on the game settings.
- Submit your response for evaluation.
- Review the AI's judgment.

This mode explores how an AI evaluates natural-language responses and attempts to distinguish truthful statements from deceptive ones. The AI's judgment is not guaranteed to be accurate.

## 🛠️ Technologies Used

- **Python** — Core programming language
- **OpenAI API** — AI-generated content and response evaluation
- **Gradio** — Interactive web-based user interface
- **Google Colab / Local Python Environment** — Development and execution environments

## 🚀 Getting Started

### Requirements

- Python 3.10 or later
- An OpenAI API key
- The `openai` and `gradio` Python packages

### 1. Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd <YOUR_REPOSITORY_NAME>
```

### 2. Install Dependencies

```bash
python -m pip install --upgrade pip
python -m pip install openai gradio
```

If the project is provided as a Jupyter Notebook, install Jupyter as well:

```bash
python -m pip install notebook
```

### 3. Configure Your OpenAI API Key

Set your API key as an environment variable.

**Windows PowerShell:**

```powershell
$env:OPENAI_API_KEY = "your-api-key"
```

**macOS / Linux:**

```bash
export OPENAI_API_KEY="your-api-key"
```

If you are using Google Colab, configure the API key through Colab Secrets or the environment-variable mechanism supported by the notebook.

**Security note:** Never commit your API key to GitHub or include it directly in publicly accessible source code.

### 4. Run the Game

If the project is provided as a Jupyter Notebook:

1. Open the notebook in Jupyter or Google Colab.
2. Execute the setup and initialization cells.
3. Execute the game interface cell.
4. Open the URL displayed in the output.

For local execution, the Gradio interface can be launched using:

```python
demo.queue().launch(
    share=False,
    server_name="127.0.0.1",
    server_port=7860,
    inbrowser=True,
)
```

The game will be available at:

http://localhost:7860/

With `share=False` and `server_name="127.0.0.1"`, the interface is intended for access from your own computer rather than through a public Gradio sharing link.

## 🔒 Privacy and Security

- The local interface is configured not to create a public Gradio sharing link.
- An internet connection is required to communicate with the OpenAI API.
- API usage may incur charges depending on the selected model and token consumption.
- Keep API keys private and use environment variables or a secrets manager to store them.

## 🔮 Future Improvements

Potential directions for future development include:

- Adding multiple difficulty levels with different game rules and AI behaviors.
- Introducing additional topics, question formats, and game scenarios.
- Improving the AI's reasoning and judgment explanations.
- Adding score tracking, replay functionality, and performance statistics.
- Improving the user interface and overall gameplay experience.

## 📌 Project Status

This project is an experimental prototype designed to explore interactive AI-based games. Features, game rules, and evaluation methods may change as development progresses.
