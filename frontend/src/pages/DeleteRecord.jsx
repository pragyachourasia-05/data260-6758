import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchListingById } from "../api/usersApi.js";

export default function DeleteRecord({ onDelete }) {
  const { id } = useParams();
  const [listing, setListing] = useState(null);

  useEffect(() => {
    async function loadListing() {
      try {
        const data = await fetchListingById(id);
        setListing(data);
      } catch {
        setListing(null);
      }
    }

    loadListing();
  }, [id]);

  async function handleDelete() {
    await onDelete(Number(id));
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="page-title">Delete Rental Listing</div>
      </div>

      <div className="card-body">
        {listing ? (
          <>
            <p>
              Delete the listing at{" "}
              <strong>{listing.property_address}</strong>?
            </p>

            <button className="btn danger" onClick={handleDelete}>
              Delete Listing
            </button>
          </>
        ) : (
          <div className="notice">Listing not found.</div>
        )}
      </div>
    </div>
  );
}