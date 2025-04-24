#!/usr/bin/env python3
import os
import sys
import argparse
import re
import base64
from github import Github
from reviewer import review_go_code
import dotenv

# Load environment variables from .env file
dotenv.load_dotenv()

def get_go_files_from_pr(repo_name, pr_number, github_token):
    """Get all Go files modified in a PR with proper diff information."""
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    
    go_files = {}
    
    # Get list of files modified in PR
    for file in pr.get_files():
        if file.filename.endswith('.go'):
            # Only process added or modified files (skip deleted)
            if file.status in ['added', 'modified']:
                # Get the full content of the file
                try:
                    file_content = repo.get_contents(file.filename, ref=pr.head.ref).decoded_content.decode('utf-8')
                except Exception as e:
                    print(f"Warning: Could not get content for {file.filename}: {str(e)}")
                    file_content = None
                
                # Parse diff to get line mapping information
                line_map = parse_diff_for_line_mapping(file.patch)
                
                go_files[file.filename] = {
                    'patch': file.patch,
                    'content': file_content,
                    'line_map': line_map,
                    'file_obj': file
                }
    
    return go_files, pr

def parse_diff_for_line_mapping(diff):
    """
    Parse git diff to map source line numbers to position in the diff.
    Returns a dictionary mapping source line numbers to positions in the diff.
    """
    if not diff:
        return {}
    
    line_map = {}
    position = 0
    source_line = 0
    
    for line in diff.split('\n'):
        position += 1
        
        # Skip diff header lines
        if line.startswith('@@'):
            # Extract the starting line number from the diff header
            # Format is like @@ -1,7 +1,7 @@
            match = re.search(r'\+(\d+)', line)
            if match:
                source_line = int(match.group(1)) - 1
            continue
        
        # Track actual file lines (skip removed lines)
        if not line.startswith('-'):
            source_line += 1
            line_map[source_line] = position
    
    return line_map

def parse_review_for_inline_comments(review_text):
    """Parse the LLM review output to extract inline comments.
    
    Format expected: 
    - Line X: Comment about this line
    - Lines X-Y: Comment about these lines
    """
    comments = []
    
    # Look for patterns like "Line X:" or "Lines X-Y:"
    line_patterns = [
        r'(?:Line|line)\s+(\d+)\s*:\s*(.*?)(?=(?:Line|line)|$)',
        r'(?:Lines|lines)\s+(\d+)-(\d+)\s*:\s*(.*?)(?=(?:Line|line)|$)'
    ]
    
    for pattern in line_patterns:
        if "Lines" in pattern or "lines" in pattern:
            # Handle range of lines
            matches = re.finditer(pattern, review_text, re.DOTALL)
            for match in matches:
                start_line = int(match.group(1))
                end_line = int(match.group(2))
                comment_text = match.group(3).strip()
                if comment_text:
                    comments.append({
                        'start_line': start_line,
                        'end_line': end_line,
                        'body': comment_text
                    })
        else:
            # Handle single line
            matches = re.finditer(pattern, review_text, re.DOTALL)
            for match in matches:
                line_num = int(match.group(1))
                comment_text = match.group(2).strip()
                if comment_text:
                    comments.append({
                        'start_line': line_num,
                        'end_line': line_num,
                        'body': comment_text
                    })
    
    # Also look for bullet points that might contain line numbers
    bullet_pattern = r'[-\*]\s+(.*?)(?=[-\*]|$)'
    bullet_matches = re.finditer(bullet_pattern, review_text, re.DOTALL)
    
    for match in bullet_matches:
        bullet_text = match.group(1).strip()
        # Check if the bullet point contains line numbers
        line_num_match = re.search(r'(?:Line|line)\s+(\d+)', bullet_text)
        if line_num_match:
            line_num = int(line_num_match.group(1))
            comments.append({
                'start_line': line_num,
                'end_line': line_num,
                'body': bullet_text
            })
    
    # If no structured comments found, use the whole review as a general comment
    if not comments and review_text.strip():
        comments.append({
            'start_line': None,
            'end_line': None,
            'body': "General feedback: " + review_text.strip()
        })
    
    return comments

def post_inline_review_comments(repo_name, pr_number, file_comments, github_token):
    """Post inline review comments to the PR using accurate position information."""
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    
    # Store comments that couldn't be posted inline
    general_comments = []
    inline_comments_count = 0
    
    # Prepare the review with comments
    comments_for_review = []
    
    for filename, file_data in file_comments.items():
        line_map = file_data.get('line_map', {})
        file_comments_list = file_data.get('comments', [])
        
        for comment in file_comments_list:
            if comment['start_line'] is not None and comment['start_line'] in line_map:
                # We have a valid position in the diff
                diff_position = line_map[comment['start_line']]
                
                # Add to comments for the review
                comments_for_review.append({
                    'path': filename,
                    'position': diff_position,
                    'body': f"Line {comment['start_line']}: {comment['body']}"
                })
                inline_comments_count += 1
            else:
                # If we can't map to a position, add as a general comment
                if comment['start_line'] is not None:
                    line_info = f"(Line {comment['start_line']})"
                else:
                    line_info = ""
                general_comments.append(f"**{filename} {line_info}:** {comment['body']}")
    
    # Create the review with all the inline comments
    if comments_for_review:
        try:
            # Create a draft review first with all comments
            review = pr.create_review(
                body="# 🤖 Go Code Review Bot\n\nDetailed feedback provided inline.",
                event="COMMENT",
                comments=comments_for_review
            )
            print(f"Added {len(comments_for_review)} inline comments to PR #{pr_number}")
        except Exception as e:
            print(f"Error creating review with inline comments: {str(e)}")
            # If the batched review fails, try adding comments one by one
            for comment in comments_for_review:
                try:
                    pr.create_review_comment(
                        body=comment['body'],
                        commit_id=pr.get_commits().reversed[0].sha,
                        path=comment['path'],
                        position=comment['position']
                    )
                    inline_comments_count += 1
                except Exception as e2:
                    print(f"Error adding comment: {str(e2)}")
                    general_comments.append(f"**{comment['path']}:** {comment['body']}")
    
    # If we have general comments, add them as a PR comment
    if general_comments:
        general_comment = "# 🤖 Go Code Review Bot\n\n"
        if inline_comments_count > 0:
            general_comment += f"Added {inline_comments_count} inline comments.\n\n"
        general_comment += "## Additional Comments\n\n"
        general_comment += "\n\n".join(general_comments)
        pr.create_issue_comment(general_comment)
    elif inline_comments_count == 0:
        pr.create_issue_comment("# 🤖 Go Code Review Bot\n\nReviewed the code but found no specific issues to comment on.")

def main():
    parser = argparse.ArgumentParser(description='Review Go code in GitHub PRs')
    parser.add_argument('--repo', required=True, help='GitHub repository in format owner/repo')
    parser.add_argument('--pr', required=True, type=int, help='Pull request number')
    parser.add_argument('--token', help='GitHub token (can also be provided via GITHUB_TOKEN env var)')
    parser.add_argument('--verbose', action='store_true', help='Print more information during execution')
    
    args = parser.parse_args()
    
    # Get GitHub token
    github_token = args.token or os.environ.get('GITHUB_TOKEN')
    if not github_token:
        print("Error: GitHub token not provided. Use --token or set GITHUB_TOKEN env var.")
        sys.exit(1)
    
    # Get modified Go files from PR
    go_files, pr = get_go_files_from_pr(args.repo, args.pr, github_token)
    
    if not go_files:
        print("No Go files found in this PR.")
        return
    
    print(f"Found {len(go_files)} Go files to review in PR #{args.pr}")
    
    # Review each Go file
    for filename, file_info in go_files.items():
        print(f"Reviewing {filename}...")
        
        # LLM-based review on the full file content if available, otherwise the patch
        content_to_review = file_info.get('content', file_info.get('patch', ''))
        if not content_to_review:
            print(f"Warning: No content to review for {filename}")
            continue
            
        review = review_go_code(content_to_review)
        
        if args.verbose:
            print(f"Raw review for {filename}:")
            print(review)
            print("-" * 40)
        
        # Parse the review for inline comments
        file_comments = parse_review_for_inline_comments(review)
        go_files[filename]['comments'] = file_comments
    
    # Post inline review comments
    post_inline_review_comments(args.repo, args.pr, go_files, github_token)

if __name__ == "__main__":
    main() 