# AI Lie Detector Game

An interactive mystery game built with Python, the OpenAI API, and Google Colab. Players interrogate AI-powered suspects, examine their statements, identify contradictions, and decide who is lying.

## Overview

In this game, a valuable painting has been stolen from a museum. There are three suspects: Tanaka (A), Sato (B), and Suzuki (C). One of them is the designated liar.

Players can ask suspects questions freely, review their previous conversations, and use the available evidence to identify the liar.

The game demonstrates how generative AI can be integrated into a simple interactive application with Python.

## Features

- **AI-powered interrogation:** Ask suspects questions using natural language.
- **Distinct suspect profiles:** Each suspect has a name, role, personality, and predefined statements.
- **Conversation history:** Maintain a separate conversation history for each suspect.
- **Rule-based answer evaluation:** Determine whether the player's final guess is correct using Python game data rather than asking the AI to decide the answer.
- **Evidence and explanations:** Display the available evidence and explain key contradictions.
- **Prompt-based consistency control:** Use system prompts to encourage suspects to follow their assigned roles and avoid inventing unsupported details.
- **Replay support:** Reset conversation histories and previous results to start another round.

## Technology Stack

- Python
- OpenAI API
- OpenAI Python SDK
- Google Colab

## Code Structure

The project is organized into notebook cells, each responsible for a specific part of the game.

| Cell | Description |
|---|---|
| Cell 1 | Loads the API key and initializes the OpenAI client. |
| Cell 2 | Defines the case, suspects, predefined statements, and evidence. |
| Cell 3 | Generates a system prompt for each suspect. |
| Cell 4 | Tests API communication and implements AI responses and conversation history management. |
| Cell 5 | Provides the interactive interrogation interface. |
| Cell 6 | Lets the player select the suspected liar and checks the answer. |
| Cell 7 | Displays the evidence and explains the key contradictions. |
| Cell 8 | Refines the system prompts and resets conversation histories. |
| Cell 9 | Optionally resets the conversation histories and previous game results for replay. |

## Getting Started

### 1. Open Google Colab

Create a new notebook or open the project notebook in Google Colab.

### 2. Configure the API key

Create an API key through the OpenAI Platform and store it in Google Colab Secrets under the name `OPENAI_API_KEY`. Enable notebook access for the secret.

Do not hardcode your API key in the notebook or commit it to GitHub.

### 3. Run the setup cells

Run Cells 1–3 in order to initialize the API client, load the game data, and generate the suspect prompts.

### 4. Test the API connection

Optionally run Cell 4 to verify that the model can answer questions and that conversation history is being recorded.

### 5. Apply the improved prompts

Run Cell 8 before starting a fresh game. This updates the prompts and clears the existing conversation histories.

### 6. Interrogate the suspects

Run Cell 5. Select suspect A, B, or C and enter questions to investigate their statements. You can switch between suspects and review their conversation histories.

Enter `終了` at the suspect-selection prompt to finish the interrogation.

### 7. Make your final guess

Run Cell 6 and select the suspect you believe is lying.

### 8. Review the result

Run Cell 7 to see whether your guess was correct and review the evidence and explanation.

### 9. Play again

Optionally run Cell 9 to clear the conversation histories and previous result. Then return to Cell 5 to begin another round.

## Game Flow

The game follows this sequence:

1. Initialize the API client and game data.
2. Generate suspect-specific system prompts.
3. Interrogate suspects and receive AI-generated responses.
4. Store conversation history separately for each suspect.
5. Select the suspected liar.
6. Evaluate the guess using predefined Python game data.
7. Display the evidence and explanation.
8. Optionally reset the game and play again.

See the accompanying flowchart image for an overview of the architecture and gameplay.

## Limitations

- The current version uses a predefined case and a fixed liar.
- Prompt instructions can reduce fabricated details and inconsistent responses, but cannot eliminate them completely.
- The evidence and final explanation are predefined rather than dynamically generated from the entire conversation.
- The notebook-based interface is intended for prototyping and experimentation, not yet as a production-ready web application.
- API usage may incur charges depending on the selected model and usage.

## Future Improvements

- Add multiple cases and randomized liar assignments.
- Improve consistency checking between suspect statements and predefined facts.
- Track which evidence the player has discovered.
- Add scoring, hints, and difficulty levels.
- Build a graphical web interface.
- Add automated tests for game logic and evidence consistency.

## Security

Keep API keys in Google Colab Secrets or another secure server-side environment. Never expose API keys in public repositories, client-side code, or screenshots.

## License

Add a license file if you intend to distribute this project for reuse. Until a license is specified, users should not assume that the repository grants permission to reuse its contents.
