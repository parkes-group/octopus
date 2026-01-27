Standard Deployment Flow (SAFE & REPEATABLE)
1️⃣ Local: Finish work on feature branch
git status
git commit -am "Your change message"

2️⃣ Local: Merge feature → main
git checkout main
git pull origin main
git merge <feature-branch-name>


✅ Must be fast-forward or clean merge
❌ If conflicts → stop and resolve locally

3️⃣ Local: Push main to GitHub
git push origin main

4️⃣ Local: Create production tag (release marker)
git tag prod-YYYY-MM-DD-short-description
git push origin prod-YYYY-MM-DD-short-description


📌 Example:

git tag prod-2026-01-26-region-count-fix

🧼 Optional (but recommended): clean up feature branch
git branch -d <feature-branch-name>
git push origin --delete <feature-branch-name>

🖥️ PythonAnywhere: Deploy to Production
5️⃣ SSH into PythonAnywhere
ssh youruser@ssh.pythonanywhere.com
cd ~/agilepricing

6️⃣ SAFETY CHECK — what will Git change?
git fetch --all --tags
git diff --name-status main origin/main

🚨 If you see:
D data/...
D app/cache/...


👉 STOP — DO NOT PULL

7️⃣ Deploy code (safe pull)
git checkout main
git pull origin main


✅ This updates code only
✅ Data stays untouched

8️⃣ Reload the web app

PythonAnywhere Dashboard → Web → Reload

🏷️ Tags: How to use them properly
✔️ Good uses

Rollbacks

Auditing releases

“What code is live?”

❌ Never do this in prod
git checkout prod-XXXX   # Detached HEAD


Tags are read-only markers, not deploy states.

⏪ Emergency Rollback (SAFE)
git fetch --all --tags
git checkout main
git reset --hard prod-YYYY-MM-DD-previous
git pull origin main


Then reload the app.

🧪 Optional: Verify prod state
git log --oneline --decorate -5


You should see:

(tag: prod-XXXX)

🚫 Commands to be VERY CAREFUL with
Command	Why
git checkout -B main	Rewrites history
git reset --hard origin/main	Can delete local state
git clean -fd	Deletes untracked files
git pull without checking diff	Can delete prod data
🛡️ Golden Rule (print this)

If Git wants to delete files you didn’t mean to delete — stop immediately.

✅ Your “Green Light Checklist”

Before pulling in prod:

 On main

 git diff --name-status main origin/main looks sane

 No data/, cache/, or logs/ deletions

 Data backed up (just in case)

 Tag created