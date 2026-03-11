from huggingface_hub import InferenceClient
from config import BASE_MODEL, MY_MODEL, HF_TOKEN
import os
from utils.tags import tag_user_input

class Chatbot:
    """
    This class is extra scaffolding around a model. Modify this class to specify how the model recieves prompts and generates responses.

    Example usage:
        chatbot = Chatbot()
        response = chatbot.get_response("What options are available for me?")
    """

    def __init__(self):
        """
        Initialize the chatbot with a HF model ID
        """
        model_id = MY_MODEL if MY_MODEL else BASE_MODEL # define MY_MODEL in config.py if you create a new model in the HuggingFace Hub
        self.client = InferenceClient(model=model_id, token=HF_TOKEN)
        # Initialize tag lists
        self.user_tags = []
        self.substance_tags = []
        
    def format_prompt(self, user_input):
        """
        Format the user's input into a proper prompt with system context.
        Also tags the input with relevant keywords and substances that appear in the text.
        
        This method:
        1. Loads system prompt from system_prompt.txt
        2. Detects keywords from keywords.txt in user input (case-insensitive, partial matches)
        3. Detects substances from substances.txt in user input (case-insensitive, partial matches)
        4. Stores tags in self.user_tags and self.substance_tags
        5. Returns formatted prompt: system_prompt + user_input + "Assistant:"

        Args:
            user_input (str): The user's question

        Returns:
            str: A formatted prompt ready for the model
        """
        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Load system prompt
        system_prompt_path = os.path.join(current_dir, 'system_prompt.txt')
        with open(system_prompt_path, 'r', encoding='utf-8') as f:
            system_prompt = f.read().strip()
        
        # Tag user input with keywords and substances
        keywords_path = os.path.join(current_dir, 'keywords.txt')
        substances_path = os.path.join(current_dir, 'substances.txt')
        
        self.user_tags = tag_user_input(keywords_path, user_input)
        self.substance_tags = tag_user_input(substances_path, user_input)
        
        # Format the prompt: system_prompt + user_input + "Assistant:"
        formatted_prompt = f"{system_prompt}\n\n{user_input}\nAssistant:"
        
        return formatted_prompt
        
    def get_response(self, user_input):
        """
        TODO: Implement this method to generate responses to user questions.
        
        This method should:
        1. Use format_prompt() to prepare the input
        2. Generate a response using the model
        3. Clean up and return the response

        Args:
            user_input (str): The user's question

        Returns:
            str: The chatbot's response

        Implementation tips:
        - Use self.format_prompt() to format the user's input
        - Use self.client to generate responses
        """
        pass
