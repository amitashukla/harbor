from huggingface_hub import InferenceClient
from src.config import BASE_MODEL, MY_MODEL, HF_TOKEN
import os
from src.utils.tags import tag_user_input
from src.utils.profile import load_schema, create_empty_profile, extract_profile_updates, merge_profile, profile_to_summary
from src.utils.resources import load_resources, filter_resources, score_resources, format_recommendations

class Chatbot:

    def __init__(self):
        """
        Initialize the chatbot with a HF model ID
        """
        model_id = MY_MODEL if MY_MODEL else BASE_MODEL # define MY_MODEL in config.py if you create a new model in the HuggingFace Hub
        self.client = InferenceClient(model=model_id, token=HF_TOKEN)
        # Initialize tag lists
        self.user_tags = []
        self.substance_tags = []
        # Initialize user profile
        current_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(current_dir, '..', 'data')
        self.profile_schema = load_schema(os.path.join(data_dir, 'user_profile_schema.json'))
        self.user_profile = create_empty_profile()
        # Load treatment resources once
        knowledge_dir = os.path.join(data_dir, '..', 'references', 'knowledge')
        resources_paths = [
            os.path.join(knowledge_dir, 'ma_resources.csv'),
            os.path.join(knowledge_dir, 'resources', 'boston_resources.csv'),
        ]
        self.resources = load_resources(resources_paths)

    def update_profile(self, user_input):
        """
        Scan user input for profile-relevant information and merge it
        into the running user profile.

        Args:
            user_input (str): The user's message text.
        """
        updates = extract_profile_updates(self.profile_schema, user_input)
        merge_profile(self.user_profile, updates)

    def format_prompt(self, user_input):
        """
        Format the user's input into a list of chat messages with system context.
        Also tags the input with relevant keywords and substances that appear in the text,
        and updates the user profile with any new information detected.

        This method:
        1. Loads system prompt from system_prompt.txt
        2. Detects keywords from keywords.txt in user input (case-insensitive, partial matches)
        3. Detects substances from substances.txt in user input (case-insensitive, partial matches)
        4. Updates user profile from schema-based keyword matching
        5. Injects profile summary into the system prompt so the model knows what's been gathered
        6. Returns a list of message dicts for the chat completion API

        Args:
            user_input (str): The user's question

        Returns:
            list[dict]: A list of message dicts with 'role' and 'content' keys
        """
        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Load system prompt
        system_prompt_path = os.path.join(current_dir, '../data/system_prompt.md')
        with open(system_prompt_path, 'r', encoding='utf-8') as f:
            system_prompt = f.read().strip()

        # Tag user input with keywords and substances
        keywords_path = os.path.join(current_dir, '../data/keywords.txt')
        substances_path = os.path.join(current_dir, '../data/substances.txt')

        self.user_tags = tag_user_input(keywords_path, user_input)
        self.substance_tags = tag_user_input(substances_path, user_input)

        # Update user profile from this message
        self.update_profile(user_input)

        # Build profile summary for the prompt
        profile_summary = profile_to_summary(self.user_profile)

        # Build system message with profile context
        system_content = system_prompt
        if profile_summary:
            system_content = system_content + "\n\n" + profile_summary

        # Return structured messages for chat completion API
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_input},
        ]

        return messages
        
    def get_response(self, user_input):
        """
        Generate a response to the user's question, with resource recommendations
        appended when the user profile contains enough information to match.

        Args:
            user_input (str): The user's question

        Returns:
            str: The chatbot's response, optionally followed by top 3 resources
        """
        # 1. Format messages (also updates profile and tags)
        messages = self.format_prompt(user_input)

        # 2. Generate LLM response via chat completion API
        result = self.client.chat_completion(
            messages=messages,
            max_tokens=512,
            temperature=0.7,
        )
        response = result.choices[0].message.content.strip()

        # 3. Filter resources by profile, score, and append top 3
        filtered = filter_resources(self.resources, self.user_profile)
        top_resources = score_resources(filtered, self.user_profile)
        recommendations = format_recommendations(top_resources)

        # Log recommendations to console
        if top_resources:
            print(f"[Harbor] Chat recommendations ({len(top_resources)}) for profile:")
            for i, r in enumerate(top_resources, 1):
                print(f"  {i}. {r.get('name', 'Unknown')} — {r.get('city', '')}, {r.get('state', '')} {r.get('zip', '')}")
        else:
            print("[Harbor] No recommendations matched current profile.")

        if recommendations:
            response = response + "\n\n" + recommendations

        return response
