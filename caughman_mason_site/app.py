from flask import Flask, render_template

app = Flask(__name__)

SITE = {
    "company_name": "Caughman Mason LLC",
    "tagline": "Construction Powerhouse",
    "email": "Jamaine@caughmanmason.com",
    "phone": "(347) 926-9541",
    "florida_note": "Expanding into Florida and preparing to bid on upcoming jobs.",
}

SERVICES = [
    {
        "title": "Construction Services",
        "description": "Construction-first execution for renovations, rehabs, property improvements, and large-scale project delivery.",
        "items": ["General contracting", "Rehab and value-add improvements", "Commercial and residential execution"],
    },
    {
        "title": "Lending Solutions",
        "description": "Investor-focused finance support for borrowers, projects, and growth-minded partners.",
        "items": ["Investor lending", "Commercial lending", "Loan officer growth opportunities"],
    },
    {
        "title": "Janitorial Services",
        "description": "Reliable janitorial and post-construction cleanup for commercial properties and active job sites.",
        "items": ["Commercial cleaning", "Post-construction cleanup", "Routine maintenance support"],
    },
    {
        "title": "Commercial Property Investing",
        "description": "Fix-and-flip, rental, and value-add commercial real estate strategy backed by execution.",
        "items": ["Fix and flip projects", "Rental portfolio growth", "Commercial repositioning"],
    },
]

CAREERS = [
    "Loan Officers",
    "Project Managers",
    "Construction Field Support",
    "Operations and Client Service Staff",
]

PROJECT_STEPS = [
    "Pre-construction planning and scope review",
    "Project execution with disciplined oversight",
    "Cleanup, turnover, and asset readiness",
    "Long-term value support through finance and investing",
]

@app.route("/")
def home():
    return render_template("index.html", site=SITE, services=SERVICES, careers=CAREERS, project_steps=PROJECT_STEPS)

@app.route("/services")
def services_page():
    return render_template("services.html", site=SITE, services=SERVICES)

@app.route("/projects")
def projects_page():
    return render_template("projects.html", site=SITE, project_steps=PROJECT_STEPS)

@app.route("/careers")
def careers_page():
    return render_template("careers.html", site=SITE, careers=CAREERS)

@app.route("/contact")
def contact_page():
    return render_template("contact.html", site=SITE)

if __name__ == "__main__":
    app.run(debug=True)