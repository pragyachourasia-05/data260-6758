import React, { useState } from "react";

export default function CreateUser({ onAdd }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    await onAdd({ name, email });
  }

  return (
    <div className="card">
        <div className="card-header">
        <div className="page-title">Add User</div>
        <div className="subtitle">Enter user details below</div>
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
            Add User
            </button>
        </form>
        </div>
    </div>
    );
}