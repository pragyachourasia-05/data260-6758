import React, { useEffect, useState } from "react";
import { login, logout, me } from "../api/usersApi.js";

export default function LoginBar({ auth, setAuth }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    async function checkSession() {
      try {
        const data = await me();

        setAuth({
          loggedIn: true,
          userId: data.user_id,
          email: data.email,
          name: data.name,
        });
      } catch {
        setAuth({
          loggedIn: false,
          userId: null,
          email: "",
          name: "",
        });
      }
    }

    checkSession();
  }, [setAuth]);

  async function handleLogin(event) {
    event.preventDefault();
    setError("");

    try {
      const data = await login(email, password);

      setAuth({
        loggedIn: true,
        userId: data.user_id,
        email: data.email,
        name: "",
      });

      setEmail("");
      setPassword("");
    } catch {
      setError("Invalid email or password.");
    }
  }

  async function handleLogout() {
    await logout();

    setAuth({
      loggedIn: false,
      userId: null,
      email: "",
      name: "",
    });
  }

  if (auth.loggedIn) {
    return (
      <div className="loginbar">
        <div className="loginbar-text">
          Logged in as <b>{auth.email}</b>
        </div>

        <button className="btn danger" onClick={handleLogout}>
          Logout
        </button>
      </div>
    );
  }

  return (
    <div className="loginbar">
      <form className="loginbar-form" onSubmit={handleLogin}>
        <div className="loginbar-text">Rental Listings Login</div>

        <input
          className="loginbar-input"
          type="email"
          placeholder="Email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />

        <input
          className="loginbar-input"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />

        <button className="btn primary" type="submit">
          Login
        </button>

        {error && <div className="notice">{error}</div>}
      </form>
    </div>
  );
}