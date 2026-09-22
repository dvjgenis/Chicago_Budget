"""Fund-type and city-function labels that stay stable as new funds and offices appear."""

from __future__ import annotations

FUND_TYPES = [
    ("corporate", "Corporate Fund", "Corporate", "local", "The city's checking account — police, fire, streets, health, City Hall."),
    ("enterprise", "Enterprise Funds", "Enterprise", "local", "Airports, water, and sewer. Paid by the people who use them."),
    ("pension", "Pension Funds", "Pension", "local", "Employer payments into the annuity and benefit funds."),
    ("special", "Special Revenue Funds", "Special revenue", "local", "Restricted pots: library, 911, vehicle tax, hotel tax, and similar."),
    ("debt", "Debt Service Funds", "Debt service", "local", "Principal and interest on city bonds and notes."),
    ("grant", "Grant Funds", "Grants", "grant", "Federal, state, and private awards."),
]

SERVICES = [
    ("safety", "Public Safety", "Police, fire, 911, and the offices that oversee them."),
    ("infra", "Infrastructure Services", "Streets, sanitation, transportation, water, and the airports."),
    ("gfr", "General Financing Requirements", "Not a department. Pensions, debt, health insurance, lawsuits, citywide bills."),
    ("admin", "Finance and Administration", "Budget, finance, law, HR, technology — and fleet and city buildings."),
    ("community", "Community Services", "Family support, public health, and the library."),
    ("develop", "City Development", "Housing, planning, and cultural affairs."),
    ("reg", "Regulatory", "Buildings, business affairs, environment, inspector general."),
    ("leg", "Legislative and Elections", "City Council and the Board of Election Commissioners."),
    ("other", "Other", "Offices that are not yet mapped to an official city function."),
]

# Official OBM program areas. New department names fall through to OTHER.
SERVICE_BY_DEPARTMENT = {
    "Chicago Police Department": "safety",
    "Chicago Fire Department": "safety",
    "Office of Emergency Management and Communications": "safety",
    "Office of Public Safety Administration": "safety",
    "Civilian Office of Police Accountability": "safety",
    "Chicago Police Board": "safety",
    "Community Commission for Public Safety and Accountability": "safety",
    "Department of Streets and Sanitation": "infra",
    "Chicago Department of Transportation": "infra",
    "Department of Water Management": "infra",
    "Chicago Department of Aviation": "infra",
    "Finance General": "gfr",
    "Office of the Mayor": "admin",
    "Office of Budget and Management": "admin",
    "Department of Technology and Innovation": "admin",
    "Office of City Clerk": "admin",
    "Department of Finance": "admin",
    "City Treasurer's Office": "admin",
    "Department of Administrative Hearings": "admin",
    "Department of Law": "admin",
    "Department of Human Resources": "admin",
    "Department of Procurement Services": "admin",
    "Department of Fleet and Facility Management": "admin",
    "Chicago Department of Public Health": "community",
    "Chicago Commission on Human Relations": "community",
    "Mayor's Office for People with Disabilities": "community",
    "Department of Family and Support Services": "community",
    "Chicago Public Library": "community",
    "Department of Housing": "develop",
    "Department of Cultural Affairs and Special Events": "develop",
    "Department of Planning and Development": "develop",
    "Office of Inspector General": "reg",
    "Department of Buildings": "reg",
    "Department of Business Affairs and Consumer Protection": "reg",
    "Department of Environment": "reg",
    "Chicago Animal Care and Control": "reg",
    "License Appeal Commission": "reg",
    "Board of Ethics": "reg",
    "City Council": "leg",
    "Board of Election Commissioners": "leg",
}

GRANT_WORDS = (
    "grant",
    "entitlement",
    "covid",
    "disaster recovery",
    "coronavirus",
    "program income",
    "protecting care",
    "fiscal recovery",
)
PENSION_WORDS = ("annuity and benefit", "pension")
ENTERPRISE_WORDS = ("water fund", "sewer fund", "o'hare", "midway", "parking meters", "airport")
DEBT_WORDS = ("bond redemption", "debt service")


def fund_type_id(fund_name: str) -> str:
    name = str(fund_name).strip().lower()
    if name == "corporate fund":
        return "corporate"
    if any(word in name for word in GRANT_WORDS):
        return "grant"
    if any(word in name for word in PENSION_WORDS):
        return "pension"
    if any(word in name for word in ENTERPRISE_WORDS):
        return "enterprise"
    if any(word in name for word in DEBT_WORDS):
        return "debt"
    return "special"


def service_id(department_name: str) -> str:
    return SERVICE_BY_DEPARTMENT.get(str(department_name).strip(), "other")


def fund_meta() -> dict[str, dict]:
    return {
        key: {
            "id": key,
            "name": name,
            "short": short,
            "group": group,
            "blurb": blurb,
            "exploreFund": name if key == "corporate" else "All funds",
        }
        for key, name, short, group, blurb in FUND_TYPES
    }


def service_meta() -> dict[str, dict]:
    return {
        key: {"id": key, "name": name, "blurb": blurb}
        for key, name, blurb in SERVICES
    }
