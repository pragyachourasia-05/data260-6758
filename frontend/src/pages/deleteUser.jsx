import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchUserById } from "../api/usersApi.js";

export default function DeleteUser({ onDelete }) {
  const { id } = useParams();
  const userId = Number(id);

  const [user, setUser] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await fetchUserById(userId);
        setUser(data);
      } catch {
        setUser(null);
      }
    })();
  }, [userId]);

  async function handleDelete() {
    await onDelete(userId);
  }

  return (
    <div className="card">
        <div className="card-header">
        <div className="page-title">Delete User</div>
        </div>

        <div className="card-body">
        {user ? (
            <>
            <p style={{ fontSize: "18px", marginBottom: "24px" }}>
                Are you sure you want to delete <strong>{user.name}</strong> ({user.email})?
            </p>

            <button className="btn danger" onClick={handleDelete}>
                Delete User
            </button>
            </>
        ) : (
            <div className="notice">
            User not found (or already deleted).
            </div>
        )}
        </div>
    </div>
    );
}