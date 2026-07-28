import os
from huggingface_hub import HfApi, create_repo
from dotenv import load_dotenv

load_dotenv()

def main():
    token = os.getenv("HF_TOKEN")
    if not token:
        print("Error: HF_TOKEN not found in .env")
        return

    api = HfApi(token=token)
    
    # Get username to construct repo id
    user_info = api.whoami()
    username = user_info["name"]
    repo_name = "llama3-8b-ecom-copywriter-lora"
    repo_id = f"{username}/{repo_name}"

    print(f"Creating repository: {repo_id}")
    try:
        create_repo(repo_id=repo_id, repo_type="model", exist_ok=True, token=token)
        print("Repository created or already exists.")
    except Exception as e:
        print(f"Failed to create repo: {e}")
        return

    folder_path = "finetuned_llama3_lora"
    print(f"Uploading files from {folder_path} to {repo_id}...")
    
    try:
        api.upload_folder(
            folder_path=folder_path,
            repo_id=repo_id,
            repo_type="model",
            token=token
        )
        print("✅ Successfully uploaded to Hugging Face Hub!")
        print(f"Model URL: https://huggingface.co/{repo_id}")
    except Exception as e:
        print(f"Upload failed: {e}")

if __name__ == "__main__":
    main()
