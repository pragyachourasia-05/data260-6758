"""HW9 Part 4: builds reference_data.json from the s6758_rel listings, plus the three question files.

    python self_improving_agents/build_datasets.py

The question files hold only questions. Expected facts live only in reference_data.json.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))
from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402

DATA = HERE / "data"


def fact(q, *nums, fields=("rent",)):
    return {"question": q, "kind": "fact", "numbers": nums, "fields": fields}


def calc(q, n, months):
    return {"question": q, "kind": "calc", "numbers": (n,), "months": months}


def compare(q, a, b):
    return {"question": q, "kind": "compare", "numbers": (a, b)}


def derived(q, *nums, value, label):
    return {"question": q, "kind": "calc", "numbers": nums, "value": value, "label": label}


def cheapest(q, *nums):
    return {"question": q, "kind": "compare", "numbers": nums}


def mixed(q, n, field, missing):
    return {"question": q, "kind": "mixed", "numbers": (n,), "fields": (field,), "unsupported": missing}


def unsupported(q):
    return {"question": q, "kind": "unsupported", "numbers": tuple(int(n) for n in re.findall(r"\b(\d{3}) Research Avenue", q))}


SPLITS = {
    "training_data": [
        fact("What is the monthly rent at 100 Research Avenue?", 100),
        fact("What type of property is 101 Research Avenue?", 101, fields=("type",)),
        fact("Give both the monthly rent and the property type for 102 Research Avenue.", 102, fields=("rent", "type")),
        calc("How much rent would I pay in total for 12 months at 103 Research Avenue?", 103, 12),
        calc("What is the total rent for 6 months at 104 Research Avenue?", 104, 6),
        compare("Which is cheaper, 105 Research Avenue or 106 Research Avenue, and by how much per month?", 105, 106),
        unsupported("Are pets allowed at 107 Research Avenue?"),
        unsupported("Does 108 Research Avenue include free parking?"),
        unsupported("Is there a gym at 109 Research Avenue?"),
        unsupported("What is the capital of France?"),
        derived("Over 12 months, how much more would 106 Research Avenue cost than 105 Research Avenue?", 105, 106, value=lambda r: abs(r[106] - r[105]) * 12, label="12 x monthly difference"),
        derived("What is the combined monthly rent of 100 Research Avenue and 101 Research Avenue?", 100, 101, value=lambda r: r[100] + r[101], label="sum of the two rents"),
        derived("If 3 roommates split the rent at 100 Research Avenue equally, how much does each pay per month?", 100, value=lambda r: r[100] // 3, label="rent / 3"),
        cheapest("Which is the cheapest of 104 Research Avenue, 102 Research Avenue and 103 Research Avenue?", 104, 102, 103),
        mixed("What is the rent at 101 Research Avenue, and are pets allowed there?", 101, "rent", "the records say nothing about pets"),
        mixed("What type of property is 103 Research Avenue, and does it have a balcony?", 103, "type", "the records say nothing about a balcony"),
    ],
    "validation_data": [
        fact("What is the monthly rent at 110 Research Avenue?", 110),
        fact("What type of property is 111 Research Avenue?", 111, fields=("type",)),
        fact("List the rent and the property type of 112 Research Avenue.", 112, fields=("rent", "type")),
        calc("How much is the total rent for 12 months at 113 Research Avenue?", 113, 12),
        calc("What would 3 months of rent cost in total at 114 Research Avenue?", 114, 3),
        compare("Which costs less per month, 115 Research Avenue or 116 Research Avenue, and what is the difference?", 115, 116),
        unsupported("Is laundry included at 117 Research Avenue?"),
        unsupported("Are utilities included in the rent at 118 Research Avenue?"),
        unsupported("Does 119 Research Avenue allow smoking?"),
        unsupported("Who wrote Pride and Prejudice?"),
        derived("Over 6 months, how much more would 116 Research Avenue cost than 115 Research Avenue?", 115, 116, value=lambda r: abs(r[116] - r[115]) * 6, label="6 x monthly difference"),
        derived("What is the combined monthly rent of 110 Research Avenue and 111 Research Avenue?", 110, 111, value=lambda r: r[110] + r[111], label="sum of the two rents"),
        derived("If 2 roommates split the rent at 112 Research Avenue equally, how much does each pay per month?", 112, value=lambda r: r[112] // 2, label="rent / 2"),
        cheapest("Which is the cheapest of 114 Research Avenue, 112 Research Avenue and 113 Research Avenue?", 114, 112, 113),
        mixed("What is the rent at 111 Research Avenue, and is parking included?", 111, "rent", "the records say nothing about parking"),
        mixed("What type of property is 113 Research Avenue, and does it have a dishwasher?", 113, "type", "the records say nothing about a dishwasher"),
    ],
    "test_data": [
        fact("What is the monthly rent at 120 Research Avenue?", 120),
        fact("Is 121 Research Avenue a house or an apartment?", 121, fields=("type",)),
        fact("Tell me the rent and the property type for 122 Research Avenue.", 122, fields=("rent", "type")),
        fact("How many units are available at 123 Research Avenue?", 123, fields=("units",)),
        calc("What is the total rent for 12 months at 124 Research Avenue?", 124, 12),
        calc("How much would 9 months of rent cost in total at 126 Research Avenue?", 126, 9),
        compare("Which is cheaper, 127 Research Avenue or 128 Research Avenue, and by how much each month?", 127, 128),
        compare("Between 129 Research Avenue and 131 Research Avenue, which has the lower rent and by how much?", 129, 131),
        unsupported("Is there a swimming pool at 132 Research Avenue?"),
        unsupported("Are dogs allowed at 133 Research Avenue?"),
        unsupported("Does 134 Research Avenue include air conditioning?"),
        unsupported("What is the tallest mountain in the world?"),
        derived("Over 9 months, how much more would 128 Research Avenue cost than 127 Research Avenue?", 127, 128, value=lambda r: abs(r[128] - r[127]) * 9, label="9 x monthly difference"),
        derived("What is the combined monthly rent of 120 Research Avenue and 121 Research Avenue?", 120, 121, value=lambda r: r[120] + r[121], label="sum of the two rents"),
        derived("If 3 roommates split the rent at 122 Research Avenue equally, how much does each pay per month?", 122, value=lambda r: r[122] // 3, label="rent / 3"),
        cheapest("Which is the cheapest of 133 Research Avenue, 131 Research Avenue and 132 Research Avenue?", 133, 131, 132),
        mixed("What is the rent at 121 Research Avenue, and is a washer included?", 121, "rent", "the records say nothing about a washer"),
        mixed("What type of property is 123 Research Avenue, and does it have a garden?", 123, "type", "the records say nothing about a garden"),
    ],
}


def money(value: int) -> list[str]:
    return [f"${value}", f"{value}", f"{value:,}", f"${value:,}"]


def main():
    numbers = sorted({n for rows in SPLITS.values() for row in rows for n in row["numbers"]})
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, property_address, monthly_rent, property_category, available_units FROM listings "
                                 "WHERE id BETWEEN 4 AND 60 ORDER BY id")).mappings().all()
    listings = {}
    for row in rows:
        number = int(row["property_address"].split()[0])
        if number in numbers and number not in listings:
            listings[number] = {"listing_id": row["id"], "address": row["property_address"],
                                "monthly_rent": int(row["monthly_rent"].split("/")[0].lstrip("$")),
                                "property_type": row["property_category"], "available_units": row["available_units"]}
    checks = {}
    DATA.mkdir(parents=True, exist_ok=True)
    for split, specs in SPLITS.items():
        items = []
        for i, spec in enumerate(specs, 1):
            qid = f"{split.split('_')[0][:3]}_{i:02d}"
            items.append({"id": qid, "question": spec["question"]})
            kind, nums = spec["kind"], spec["numbers"]
            required, labels, forbid = [], [], ""
            if kind in ("fact", "mixed"):
                row = listings[nums[0]]
                if "rent" in spec["fields"]:
                    required.append(money(row["monthly_rent"]))
                    labels.append(f"monthly rent ${row['monthly_rent']}")
                if "type" in spec["fields"]:
                    required.append([row["property_type"]])
                    labels.append(f"property type {row['property_type']}")
                if "units" in spec["fields"]:
                    required.append([str(row["available_units"]), "one"])
                    labels.append(f"{row['available_units']} available unit(s)")
            elif kind == "calc" and "value" in spec:
                value = spec["value"]({n: listings[n]["monthly_rent"] for n in nums})
                required.append(money(value))
                labels.append(f"{spec['label']} = ${value}")
            elif kind == "calc":
                rent = listings[nums[0]]["monthly_rent"]
                required.append(money(rent * spec["months"]))
                labels.append(f"total {spec['months']} x ${rent} = ${rent * spec['months']}")
            elif kind == "compare" and len(nums) > 2:
                low = min(nums, key=lambda n: listings[n]["monthly_rent"])
                rent = listings[low]["monthly_rent"]
                required += [[str(low)], money(rent)]
                labels += [f"cheapest listing is {low} Research Avenue", f"its rent is ${rent}"]
            elif kind == "compare":
                a, b = listings[nums[0]], listings[nums[1]]
                low = nums[0] if a["monthly_rent"] <= b["monthly_rent"] else nums[1]
                diff = abs(a["monthly_rent"] - b["monthly_rent"])
                required += [[str(low)], money(diff)]
                labels += [f"cheaper listing is {low} Research Avenue", f"difference ${diff} per month"]
                high = nums[1] if low == nums[0] else nums[0]
                forbid = rf"\b{high} Research Avenue[^.]{{0,40}}\b(is|costs?|has)\b[^.]{{0,25}}\b(cheaper|less|lower)\b"
            checks[qid] = {"kind": kind, "required_any_of": required, "facts": labels, "forbid": forbid}
            if kind == "mixed":
                checks[qid]["unsupported"] = spec["unsupported"]
            checks[qid]["has_listing"] = bool(nums)
        (DATA / f"{split}.json").write_text(json.dumps(items, indent=2), encoding="utf-8")
    reference = {"source": "s6758_rel.listings", "listings": listings, "checks": checks,
                 "note": "kind=unsupported means the listing records do not contain the answer, so the correct answer says so."}
    (DATA / "reference_data.json").write_text(json.dumps(reference, indent=2), encoding="utf-8")
    print(f"listings={len(listings)} checks={len(checks)} missing={sorted(set(numbers) - set(listings))}")


if __name__ == "__main__":
    main()
