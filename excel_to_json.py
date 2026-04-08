import os
import pandas as pd
import json

# =========================
# CONFIG
# =========================

EXCEL_FOLDER = "excel_files"
JSON_FOLDER = "json_files"

os.makedirs(JSON_FOLDER, exist_ok=True)

# =========================
# Helper: Clean DataFrame
# =========================

def df_to_json(df):
    df.columns = df.columns.str.strip().str.lower()
    # Convert NaN to None (becomes null in JSON)
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient="records")

# =========================
# 1. Convert Company Files (od_tp_*.xlsx)
# =========================

def convert_company_files():
    print("\n📁 Converting Company Files...")

    for file in os.listdir(EXCEL_FOLDER):
        if file.endswith(".xlsx") and file.startswith("od_tp_"):
            file_path = os.path.join(EXCEL_FOLDER, file)
            company_name = file.lower().replace(".xlsx", "")  # e.g. od_tp_shriram

            print(f"  ➡️  Processing: {file}")

            df = pd.read_excel(file_path)
            records = df_to_json(df)

            out_path = os.path.join(JSON_FOLDER, f"{company_name}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, default=str)

            print(f"  ✅ Saved: {out_path}  ({len(records)} records)")

# =========================
# 2. Convert Masters File (masters.xlsx)
# =========================

def convert_masters_file():
    print("\n📁 Converting Masters File...")

    master_path = os.path.join(EXCEL_FOLDER, "masters.xlsx")

    if not os.path.exists(master_path):
        print("  ❌ masters.xlsx not found → skipping")
        return

    xl = pd.ExcelFile(master_path)
    print(f"  📋 Sheets found: {xl.sheet_names}")

    masters_out = {}

    for sheet in xl.sheet_names:
        print(f"  ➡️  Processing sheet: {sheet}")
        df = pd.read_excel(master_path, sheet_name=sheet)
        records = df_to_json(df)
        sheet_key = sheet.strip().lower().replace(" ", "_")
        masters_out[sheet_key] = records
        print(f"     ✅ {len(records)} records")

    # Save all sheets into one masters.json
    out_path = os.path.join(JSON_FOLDER, "masters.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(masters_out, f, indent=2, default=str)

    print(f"\n  ✅ Saved: {out_path}")

    # Also save vehicle_type sheet as separate file (used frequently)
    vehicle_key = None
    for sheet in xl.sheet_names:
        if "vehicle" in sheet.lower() and "type" in sheet.lower():
            vehicle_key = sheet.strip().lower().replace(" ", "_")
            break

    if vehicle_key and vehicle_key in masters_out:
        veh_path = os.path.join(JSON_FOLDER, "vehicle_type_master.json")
        with open(veh_path, "w", encoding="utf-8") as f:
            json.dump(masters_out[vehicle_key], f, indent=2, default=str)
        print(f"  ✅ Also saved separately: {veh_path}")

# =========================
# 3. Convert RTO Mapping File
# =========================

def convert_rto_mapping():
    print("\n📁 Converting RTO Mapping File...")

    rto_path = os.path.join(EXCEL_FOLDER, "rto_mapping.xlsx")

    if not os.path.exists(rto_path):
        print("  ❌ rto_mapping.xlsx not found → skipping")
        return

    df = pd.read_excel(rto_path)
    records = df_to_json(df)

    out_path = os.path.join(JSON_FOLDER, "rto_mapping.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)

    print(f"  ✅ Saved: {out_path}  ({len(records)} records)")

# =========================
# MAIN
# =========================

if __name__ == "__main__":
    print("🚀 Starting Excel → JSON Conversion...\n")

    convert_company_files()
    convert_masters_file()
    convert_rto_mapping()

    print("\n🎉 All Done! JSON files saved in:", JSON_FOLDER)