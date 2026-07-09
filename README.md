# AI-Based Career Guidance System

A Flask web application that helps students explore suitable career paths based on their skills and interests.

## Features
- Secure login/signup with hashed passwords and session management
- Home page with quick navigation to all modules
- Dashboard with personal statistics and recent activity
- Career Search with guidance, salary ranges, and roadmaps
- Search History (per-user, stored in JSON)
- Profile management (update email/password)
- Reports & Analytics with Chart.js visualizations
- Admin panel for user management (add/edit/delete users)

## Tech Stack
- Python, Flask
- HTML, CSS, JavaScript, Bootstrap 5
- Chart.js for analytics
- JSON files for data storage (no database required)

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** in your browser. The Login page is the default landing page.

## Default Admin Login
- Username: `admin`
- Password: `admin123`

(Created automatically the first time you run the app.)

## Project Structure
```
career_guidance/
├── app.py
├── requirements.txt
├── data/
│   ├── users.json
│   ├── history.json
│   └── careers.json
├── templates/
│   ├── base.html, login.html, signup.html, home.html,
│   ├── dashboard.html, career_search.html, history.html,
│   ├── profile.html, reports.html, admin_users.html, 404.html
└── static/
    └── css/style.css
```

## Future Enhancements
- Integrate a MySQL database
- Add AI-based recommendation engine
- Add aptitude/skill assessment tests
- Deploy to the cloud
- Build a richer admin analytics dashboard
