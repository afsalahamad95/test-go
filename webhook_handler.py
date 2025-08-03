from flask import Flask, request, jsonify
import hmac
import hashlib
import json
import os
from github_pr_reviewer import main as review_pr
import dotenv
from github import Github

dotenv.load_dotenv()

app = Flask(__name__)

# Get webhook secret from environment variable
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')

def verify_webhook_signature(payload, signature):
    """Verify the webhook signature from GitHub."""
    if not WEBHOOK_SECRET:
        return False
    
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected_signature}", signature)

def should_skip_review(payload):
    """Check if the review should be skipped based on commit messages."""
    # Get the latest commit message
    pr = payload.get('pull_request', {})
    if not pr:
        return False
    
    # Get the GitHub token from environment
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        return False
    
    # Initialize GitHub client
    g = Github(github_token)
    
    # Get the repository and PR
    repo_name = payload.get('repository', {}).get('full_name')
    pr_number = pr.get('number')
    
    if not repo_name or not pr_number:
        return False
    
    try:
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        
        # Check the title and body of the PR
        pr_title = pr.title.lower()
        pr_body = pr.body.lower() if pr.body else ""
        
        # Check all commit messages in the PR
        for commit in pr.get_commits():
            commit_message = commit.commit.message.lower()
            if any(keyword in commit_message for keyword in ['[ignore]', '[skip review]', '[no review]']):
                return True
        
        # Also check PR title and body
        if any(keyword in pr_title or keyword in pr_body for keyword in ['[ignore]', '[skip review]', '[no review]']):
            return True
            
    except Exception as e:
        print(f"Error checking commit messages: {str(e)}")
        return False
    
    return False

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    # Get the signature from the request headers
    signature = request.headers.get('X-Hub-Signature-256')
    if not signature:
        return jsonify({'error': 'No signature provided'}), 401
    
    # Verify the webhook signature
    if not verify_webhook_signature(request.get_data(), signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Parse the webhook payload
    payload = request.json
    
    # Check if this is a PR event
    if request.headers.get('X-GitHub-Event') == 'pull_request':
        action = payload.get('action')
        
        # Only process when PR is opened or reopened
        if action in ['opened', 'reopened']:
            # Check if we should skip the review
            if should_skip_review(payload):
                return jsonify({'message': 'Review skipped due to [ignore] in commit message'}), 200
                
            pr = payload.get('pull_request')
            repo = payload.get('repository')
            
            if pr and repo:
                # Extract necessary information
                repo_name = repo.get('full_name')
                pr_number = pr.get('number')
                
                # Trigger the PR review
                try:
                    review_pr(repo_name, pr_number)
                    return jsonify({'message': 'PR review triggered successfully'}), 200
                except Exception as e:
                    return jsonify({'error': str(e)}), 500
    
    return jsonify({'message': 'Webhook received but no action taken'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=12000) 