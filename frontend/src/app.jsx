import React, { useEffect, useState } from "react";
import { Routes, Route, useNavigate } from "react-router-dom";

import Navbar from "./components/Navbar.jsx";
import LoginBar from "./components/LoginBar.jsx";
import Home from "./pages/Home.jsx";
import CreateRecord from "./pages/CreateRecord.jsx";
import UpdateRecord from "./pages/UpdateRecord.jsx";
import DeleteRecord from "./pages/DeleteRecord.jsx";

import {
  fetchListings,
  createListing,
  updateListing,
  deleteListing,
} from "./api/usersApi.js";

function RequireAuth({ auth, children }) {
  if (!auth.loggedIn) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="page-title">Login Required</div>
        </div>
        <div className="card-body">
          <div className="notice">
            Please log in to view and manage rental listings.
          </div>
        </div>
      </div>
    );
  }

  return children;
}

export default function App() {
  const navigate = useNavigate();

  const [auth, setAuth] = useState({
    loggedIn: false,
    userId: null,
    email: "",
    name: "",
  });

  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function loadListings() {
      if (!auth.loggedIn) {
        setListings([]);
        return;
      }

      try {
        setLoading(true);
        const data = await fetchListings();
        setListings(data);
      } catch (error) {
        console.error("Could not load listings:", error);
      } finally {
        setLoading(false);
      }
    }

    loadListings();
  }, [auth.loggedIn]);

  async function handleCreate(payload) {
    const created = await createListing(payload);
    setListings((previous) => [...previous, created]);
    navigate("/");
  }

  async function handleUpdate(id, payload) {
    const updated = await updateListing(id, payload);

    setListings((previous) =>
      previous.map((listing) =>
        listing.id === id ? updated : listing
      )
    );

    navigate("/");
  }

  async function handleDelete(id) {
    await deleteListing(id);

    setListings((previous) =>
      previous.filter((listing) => listing.id !== id)
    );

    navigate("/");
  }

  return (
    <div className="container">
      <Navbar auth={auth} />
      <LoginBar auth={auth} setAuth={setAuth} />

      <Routes>
        <Route
          path="/"
          element={
            <Home
              listings={listings}
              loading={loading}
              auth={auth}
            />
          }
        />

        <Route
          path="/create"
          element={
            <RequireAuth auth={auth}>
              <CreateRecord onCreate={handleCreate} />
            </RequireAuth>
          }
        />

        <Route
          path="/update/:id"
          element={
            <RequireAuth auth={auth}>
              <UpdateRecord onUpdate={handleUpdate} />
            </RequireAuth>
          }
        />

        <Route
          path="/delete/:id"
          element={
            <RequireAuth auth={auth}>
              <DeleteRecord onDelete={handleDelete} />
            </RequireAuth>
          }
        />
      </Routes>
    </div>
  );
}