import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchUserById } from "../api/usersApi.js";

export default function UpdateUser({ onUpdate }) {
  const { id } = useParams();
  const userId = Number(id);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const user = await fetchUserById(userId);
        setName(user.name);
        setEmail(user.email);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    })();
  }, [userId]);

  async function handleSubmit(e) {
    e.preventDefault();
    await onUpdate(userId, { name, email });
  }

  if (loading) return <p>Loading user...</p>;

  return (
    <div className="card">
        <div className="card-header">
        <div className="page-title">Update User (ID: {userId})</div>
        </div>

        <div className="card-body">
        <form className="form" onSubmit={handleSubmit}>
            <label>
            Name
            <input
                value={name}
                onChange={(e) => setName(e.target.value)}
            />
            </label>

            <label>
            Email
            <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
            />
            </label>

            <button className="btn primary" type="submit">
            Update User
            </button>
        </form>
        </div>
    </div>
    );
}