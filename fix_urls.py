import os

path = r"c:\Users\HP\Desktop\TRY0\carbonhero\app\templates"

replacements = {
    "url_for('home')": "url_for('main.home')",
    "url_for('dashboard')": "url_for('main.dashboard')",
    "url_for('signup')": "url_for('auth.signup')",
    "url_for('login')": "url_for('auth.login')",
    "url_for('logout')": "url_for('auth.logout')",
    "url_for('log_entry')": "url_for('logger.log_entry')",
    "url_for('boss_arena')": "url_for('arena.boss_arena')",
    "url_for('leaderboard')": "url_for('arena.leaderboard')",
    "url_for('achievements')": "url_for('arena.achievements')",
    "url_for('environmental_news')": "url_for('arena.environmental_news')",
    "url_for('api_insights')": "url_for('api.api_insights')",
    "url_for('api_chat')": "url_for('api.api_chat')",
    
    "request.endpoint == 'home'": "request.endpoint == 'main.home'",
    "request.endpoint == 'dashboard'": "request.endpoint == 'main.dashboard'",
    "request.endpoint == 'log_entry'": "request.endpoint == 'logger.log_entry'",
    "request.endpoint == 'leaderboard'": "request.endpoint == 'arena.leaderboard'",
    "request.endpoint == 'achievements'": "request.endpoint == 'arena.achievements'",
    "request.endpoint == 'environmental_news'": "request.endpoint == 'arena.environmental_news'"
}

for root, _, files in os.walk(path):
    for f in files:
        if f.endswith(".html"):
            fp = os.path.join(root, f)
            with open(fp, "r", encoding="utf-8") as file:
                content = file.read()
            for old, new in replacements.items():
                content = content.replace(old, new)
            with open(fp, "w", encoding="utf-8") as file:
                file.write(content)
print("Done fixing URLs")
