from flask import Flask, render_template, request, jsonify
import sys
import os
import time
import re
from rule_engine import run_engine
from query_engine import extract_params_from_query, apply_company_exclusions

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)

# Company aliases
COMPANY_ALIASES = {
    "sbi": ["sbi", "sbi general"],
    "tata": ["tata aig","tata"],
    "hdfc": ["hdfc", "hdfc ergo"],
    "digit": ["digit", "go digit"],
    "liberty": ["liberty"],
    "shriram": ["shriram","shriram general"],
    "sompo": ["sompo","universal","sompo general"],
    "bajaj": ["bajaj allianz","bajaj"],
    "icici": ["icici", "icici lombard"],
    "reliance": ["reliance"],
    "new india": ["new india","new india assurance"],
    "future": ["future", "future generali"],
    "kotak": ["kotak", "kotak mahindra"],
    "magma": ["magma", "magma hdi"],
    "royal": ["royal sundaram","royal"],
    "chola": ["chola", "cholamandalam"],
    "zuno": ["zuno"],
}


def detect_requested_companies(user_query):
    query_lower = user_query.lower()
    found = []
    for company, aliases in COMPANY_ALIASES.items():
        if any(alias in query_lower for alias in aliases):
            found.append(company)
    return found


def run_for_company(company, params):
    from rule_engine import run_engine
    try:
        results = run_engine(
            company=company,
            sub_product=params.get("sub_product", ""),
            segment=params.get("segment", "comp"),
            rto=params.get("rto", "pan india"),
            fuel=params.get("fuel", ""),
            ncb=params.get("ncb", ""),
            highend=params.get("highend", ""),
            cpa=params.get("cpa", ""),
            vehicle_make=params.get("vehicle_make", ""),
            cc=params.get("cc", ""),
            seating=params.get("seating", ""),
            weight=params.get("weight", ""),
            age=params.get("age", ""),
            nil_dep=params.get("nil_dep", ""),
            wheels=params.get("wheels", "")
        )
        return results or [], None
    except Exception as e:
        return [], str(e)


def clean_result(r, company_fallback, mode, rank=None):
    return {
        "company": r.get("_company_source", company_fallback).upper(),
        "row_id": str(r.get("id", "N/A")),
        "vehicle_type_id": str(r.get("vehicle_type_id", "N/A")),
        "od_rate": float(r.get("payout_od_rate", 0) or 0),
        "tp_rate": float(r.get("payout_tp_rate", 0) or 0),
        "valid_from": str(r.get("eff_from_date", "")),
        "valid_to": str(r.get("eff_to_date", "")),
        "difference": str(r.get("difference", "")),
        "mode": mode,
        "rank": rank
    }

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/getRates", methods=["POST"])
def get_rates():
    try:
        data = request.get_json()
        user_query = data.get("query", "").strip()

        if not user_query:
            return jsonify({"status": "error", "message": "Query required"}), 400

        start_time = time.time()

        from query_engine import extract_params_from_query, apply_company_exclusions

        params = extract_params_from_query(user_query)

        query_lower = user_query.lower()

        # TOP N FIX
        top_match = re.search(r"top\s*(\d+)", query_lower)
        top_n = int(top_match.group(1)) if top_match else 5

        # existing overrides (same as your code)
        seating_plus = re.findall(r'\((\d+)\+(\d+)\)', user_query)
        if seating_plus:
            params["seating"] = str(int(seating_plus[0][0]) + int(seating_plus[0][1]))

        setting_match = re.findall(r'setting\s*=?\s*(\d+)', query_lower)
        if setting_match:
            params["seating"] = setting_match[0]

        wheel_match = re.findall(r'\b(\d+)\s*w\b', query_lower)
        if wheel_match:
            params["wheels"] = wheel_match[0]

        if "gvw" in query_lower:
            params["sub_product"] = "gvw"

        params = apply_company_exclusions(params, user_query)

        requested = detect_requested_companies(user_query)
        engine_co = params.get("company", "all")
        excluded = params.get("excluded_companies", [])

        final_results = []

        # MODE A: ALL companies → TOP N
        if engine_co == "all" and len(requested) == 0:
            results, _ = run_for_company("all", params)

            if excluded:
                results = [
                    r for r in results
                    if not any(ex in r.get("_company_source", "").lower() for ex in excluded)
                ]

            best_per_company = {}
            for r in results:
                co = r.get("_company_source", "unknown")
                if co not in best_per_company or r["payout_od_rate"] > best_per_company[co]["payout_od_rate"]:
                    best_per_company[co] = r

            sorted_results = sorted(
                best_per_company.values(),
                key=lambda x: (x.get("payout_od_rate", 0) or 0),
                reverse=True
            )[:top_n]

            for i, r in enumerate(sorted_results, 1):
                final_results.append(clean_result(r, "all", "top", i))

        # MODE B: multiple companies
        elif len(requested) >= 2:
            for co in requested:
                results, _ = run_for_company(co, params)
                if results:
                    final_results.append(clean_result(results[0], co, "multi"))

        # MODE C: single
        else:
            results, _ = run_for_company(engine_co, params)
            if results:
                for r in results[:top_n]:
                    final_results.append(clean_result(r, engine_co, "single"))

        elapsed = round((time.time() - start_time) * 1000)

        return jsonify({
            "status": "success",
            "query": user_query,
            "results": final_results,
            "count": len(final_results),
            "time_ms": elapsed
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)

# To test, use the following curl command (or use Postman):
# http://localhost:5000/getRates