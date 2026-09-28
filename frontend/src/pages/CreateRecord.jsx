import React, { useState } from "react";

const initialForm = {
  property_address: "",
  monthly_rent: "",
  submitter_email: "",
  listing_description: "",
  property_category: "",
};

export default function CreateRecord({ onCreate }) {
  const [form, setForm] = useState(initialForm);

  function handleChange(event) {
    setForm({
      ...form,
      [event.target.name]: event.target.value,
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    await onCreate(form);
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="page-title">Add Rental Listing</div>
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
              placeholder="$3500/month"
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
              placeholder="Apartment or House"
              value={form.property_category}
              onChange={handleChange}
              required
            />
          </label>

          <button className="btn primary" type="submit">
            Add Listing
          </button>
        </form>
      </div>
    </div>
  );
}