import React from "react";
import { Link } from "react-router-dom";

export default function Home({ listings, loading, auth }) {
  if (!auth.loggedIn) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="page-title">Rental Housing Listings</div>
        </div>

        <div className="card-body">
          <div className="notice">
            Login required to view rental listings.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="page-title">Rental Housing Listings</div>
          <div className="subtitle">
            Listings are stored in MySQL and available only to logged-in users.
          </div>
        </div>

        <Link className="btn primary" to="/create">
          Add Listing
        </Link>
      </div>

      <div className="card-body">
        {loading ? (
          <div className="notice">Loading listings...</div>
        ) : listings.length === 0 ? (
          <div className="notice">
            No listings found. Add your first rental listing.
          </div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Property Address</th>
                  <th>Monthly Rent</th>
                  <th>Category</th>
                  <th>Description</th>
                  <th>Actions</th>
                </tr>
              </thead>

              <tbody>
                {listings.map((listing) => (
                  <tr key={listing.id}>
                    <td>{listing.id}</td>
                    <td>{listing.property_address}</td>
                    <td>{listing.monthly_rent}</td>
                    <td>{listing.property_category}</td>
                    <td>{listing.listing_description}</td>
                    <td className="actions">
                      <Link
                        className="btn"
                        to={`/update/${listing.id}`}
                      >
                        Update
                      </Link>

                      <Link
                        className="btn danger"
                        to={`/delete/${listing.id}`}
                      >
                        Delete
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}