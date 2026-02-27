@partners_bp.route("/dashboard")
@role_required("partner")
def dashboard():
    partner = Partner.query.filter_by(user_id=current_user.id).first()

    dashboards = {
        "contractor": "partners/dashboards/contractor.html",
        "designer": "partners/dashboards/designer.html",
        "cleaner": "partners/dashboards/cleaner.html",
        "janitorial": "partners/dashboards/cleaner.html",
        "realtor": "partners/dashboards/realtor.html",
        "inspector": "partners/dashboards/inspector.html",
        "appraiser": "partners/dashboards/appraiser.html",
        "title": "partners/dashboards/title.html",
        "insurance": "partners/dashboards/insurance.html",
        "attorney": "partners/dashboards/attorney.html",
        "property_manager": "partners/dashboards/property_manager.html",
    }

    template = dashboards.get(partner.role, "partners/dashboards/default.html")
    return render_template(template, partner=partner)

@partners_bp.route("/")
@role_required("partner")
def center():
    role_filter = request.args.get("role")
    query = Partner.query

    if role_filter:
        query = query.filter_by(role=role_filter)

    partners = query.all()

    return render_template(
        "partners/center.html",
        partners=partners,
        role_filter=role_filter
    )

@partners_bp.route("/<int:partner_id>")
@login_required
def profile(partner_id):
    partner = Partner.query.get_or_404(partner_id)
    return render_template("partners/profile.html", partner=partner)

@partners_bp.route("/register", methods=["GET", "POST"])
@login_required
def register():
    if request.method == "POST":
        role = request.form.get("role")
        company = request.form.get("company")
        specialty = request.form.get("specialty")
        service_area = request.form.get("service_area")
        bio = request.form.get("bio")

        partner = Partner(
            user_id=current_user.id,
            role=role,
            company=company,
            specialty=specialty,
            service_area=service_area,
            bio=bio
        )
        db.session.add(partner)
        db.session.commit()

        return redirect(url_for("partners.dashboard"))

    return render_template("partners/register.html")
