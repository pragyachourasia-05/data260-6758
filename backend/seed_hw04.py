import random

from app.database import SessionLocal
from app.models import Listing, ListingDetail


SEED = 6758
TARGET_LISTINGS = 5000
TARGET_DETAILS = 200


def main():
    random.seed(SEED)

    with SessionLocal() as db:
        listing_count = db.query(Listing).count()
        detail_count = db.query(ListingDetail).count()

        print(f"Existing listings: {listing_count}")
        print(f"Existing details: {detail_count}")

        listings_to_add = max(0, TARGET_LISTINGS - listing_count)

        for index in range(listings_to_add):
            db.add(
                Listing(
                    property_address=(
                        f"{100 + index} Research Avenue, San Jose, CA"
                    ),
                    monthly_rent=f"${1800 + (index % 25) * 75}/month",
                    submitter_email="benchmark@sjsu.edu",
                    listing_description=(
                        f"Deterministic benchmark rental listing {index + 1}. "
                        "Near transit and local services."
                    ),
                    property_category=(
                        "Apartment" if index % 2 == 0 else "House"
                    ),
                )
            )

            if (index + 1) % 500 == 0:
                db.commit()
                print(f"Added {index + 1} listings")

        db.commit()

        listings = (
            db.query(Listing)
            .order_by(Listing.id.asc())
            .limit(TARGET_DETAILS)
            .all()
        )

        details_to_add = max(0, TARGET_DETAILS - detail_count)

        for index in range(details_to_add):
            db.add(
                ListingDetail(
                    listing_id=listings[index % len(listings)].id,
                    detail_name="amenity",
                    detail_value=(
                        "Parking" if index % 2 == 0 else "Laundry"
                    ),
                )
            )

            if (index + 1) % 50 == 0:
                db.commit()
                print(f"Added {index + 1} related details")

        db.commit()
        print(f"Final listings: {db.query(Listing).count()}")
        print(f"Final details: {db.query(ListingDetail).count()}")


if __name__ == "__main__":
    main()
