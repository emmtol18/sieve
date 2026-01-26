# Project Guidance

## Workflow Instructions

### Git Worktrees (Required for Feature Work)

**Always use git worktrees** for feature development, bug fixes, or any work that benefits from isolation.

**Worktree directory:** `.worktrees/` (project-local, hidden)

**Workflow:**

1. **Create worktree** for new work:
   ```bash
   git worktree add .worktrees/<branch-name> -b <branch-name>
   cd .worktrees/<branch-name>
   ```

2. **Run project setup** after creating:
   ```bash
   npm install  # or appropriate setup command
   ```

3. **Verify clean baseline** - run tests before starting work

4. **When finished** - use the `finishing-a-development-branch` skill for proper cleanup

**Why:** Worktrees provide isolation, allow parallel work on multiple features, and keep the main workspace clean.

### After Completing a Feature or Change

Always conclude work on a feature, bug fix, or any code change with:

1. **Git commit message suggestion** - Provide a clear, conventional commit message following this format:
   ```
   <type>: <short description>

   <optional body explaining what and why>
   ```
   Types: `feat`, `fix`, `refactor`, `docs`, `style`, `test`, `chore`

2. **Summary of changes** - List what files were modified/created and what changed:
   - Files added
   - Files modified
   - Key changes made
   - Any breaking changes or important notes

### Example

```
Suggested commit:
feat: add user authentication with JWT tokens

Changes made:
- Created: src/auth/jwt.ts (JWT token generation/validation)
- Modified: src/routes/api.ts (added auth middleware)
- Modified: src/types/user.ts (added token fields)
```
