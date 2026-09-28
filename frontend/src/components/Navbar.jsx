import React from "react";
import { Link, NavLink } from "react-router-dom";

export default function Navbar({ auth }) {
  return (
    <header className="navbar">
      <Link className="brand" to="/">
        <span className="brand-badge" />
        Rental Housing Listings
      </Link>

      <nav className="navlinks">
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            isActive ? "active" : ""
          }
        >
          Home
        </NavLink>

        {auth.loggedIn && (
          <NavLink
            to="/create"
            className={({ isActive }) =>
              isActive ? "active" : ""
            }
          >
            Add Listing
          </NavLink>
        )}
      </nav>
    </header>
  );
}