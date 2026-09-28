import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchListingById } from "../api/usersApi.js";

export default function UpdateRecord({ onUpdate }) {
  const { id } = useParams();

  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadListing() {
      try {
        const data = await fetchListingById(id);

        setForm({
          property_address: data.property_address,
          monthly_rent: data.monthly_rent,
          submitter_email: data.submitter_email,
          listing_description: data.listing_description,
          property_category: data.property_category,
        });
      } finally {
        setLoading(false);
      }
    }

    loadListing();
  }, [id]);

  function handleChange(event) {
    setForm({
      ...form,
      [event.target.name]: event.target.value,
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    await onUpdate(Number(id), form);
  }

  if (loading) {
    return <div className="notice">Loading listing...</div>;
  }

  if (!form) {
    return <div className="notice">Listing not found.</div>;
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="page-title">
          Update Rental Listing {id}
        </div>
      </div>

      <div className="card-body">
        <form className="form" onSubmit={handleSubmit}>
          <label>
            Property Address
            <input
              name="property_address"
              value={form.property_address}
              onChange={handleChange}
              required
            />
          </label>

          <label>
            Monthly Rent
            <input
              name="monthly_rent"
              value={form.monthly_rent}
              onChange={handleChange}
              required
            />
          </label>

          <label>
            Submitter Email
            <input
              name="submitter_email"
              type="email"
              value={form.submitter_email}
              onChange={handleChange}
              required
            />
          </label>

          <label>
            Listing Description
            <input
              name="listing_description"
              value={form.listing_description}
              onChange={handleChange}
              required
            />
          </label>

          <label>
            Property Category
            <input
              name="property_category"
              value={form.property_category}
              onChange={handleChange}
              required
            />
          </label>

          <button className="btn primary" type="submit">
            Update Listing
          </button>
        </form>
      </div>
    </div>
  );
}