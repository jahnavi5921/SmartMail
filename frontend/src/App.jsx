import { useEffect, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [activeSection, setActiveSection] = useState("all");

  const [emails, setEmails] = useState([]);
  const [rules, setRules] = useState([]);

  const [ruleType, setRuleType] = useState("keyword");
  const [ruleValue, setRuleValue] = useState("");
  const [editingRuleId, setEditingRuleId] = useState(null);

  const [loadingEmails, setLoadingEmails] = useState(true);
  const [loadingRules, setLoadingRules] = useState(true);
  const [syncing, setSyncing] = useState(false);

  // =====================================================
  // LOAD EMAILS
  // =====================================================

  const loadEmails = async () => {
    try {
      setLoadingEmails(true);

      const response = await fetch(
        `${API_URL}/api/emails`
      );

      if (!response.ok) {
        throw new Error("Failed to load emails");
      }

      const data = await response.json();

      setEmails(data.emails || []);
    } catch (error) {
      console.error(
        "Failed to load emails:",
        error
      );

      setEmails([]);
    } finally {
      setLoadingEmails(false);
    }
  };

  // =====================================================
  // LOAD RULES
  // =====================================================

  const loadRules = async () => {
    try {
      setLoadingRules(true);

      const response = await fetch(
        `${API_URL}/api/rules`
      );

      if (!response.ok) {
        throw new Error("Failed to load rules");
      }

      const data = await response.json();

      setRules(data.rules || []);
    } catch (error) {
      console.error(
        "Failed to load rules:",
        error
      );

      setRules([]);
    } finally {
      setLoadingRules(false);
    }
  };

  // =====================================================
  // INITIAL LOAD
  // =====================================================

  useEffect(() => {
    loadEmails();
    loadRules();
  }, []);

  // =====================================================
  // IMPORTANT EMAIL CHECK
  // =====================================================

  const isImportant = (email) => {
    return rules.some((rule) => {
      const ruleValue = (
        rule.rule_value || ""
      ).toLowerCase();

      const sender = (
        email.sender || ""
      ).toLowerCase();

      const subject = (
        email.subject || ""
      ).toLowerCase();

      const body = (
        email.body || ""
      ).toLowerCase();

      if (rule.rule_type === "keyword") {
        return (
          subject.includes(ruleValue) ||
          body.includes(ruleValue)
        );
      }

      if (rule.rule_type === "sender") {
        return sender.includes(ruleValue);
      }

      return false;
    });
  };

  const importantEmails =
    emails.filter(isImportant);

  const displayedEmails =
    activeSection === "important"
      ? importantEmails
      : emails;

  // =====================================================
  // CONNECT / CHOOSE GMAIL ACCOUNT
  // =====================================================

  const handleConnectGmail = () => {
    window.location.href =
      `${API_URL}/auth/login`;
  };

  // =====================================================
  // GMAIL SYNC
  // =====================================================

  const handleSync = async () => {
    try {
      setSyncing(true);

      const response = await fetch(
        `${API_URL}/api/gmail/sync`,
        {
          method: "POST",
        }
      );

      if (!response.ok) {
        const errorData =
          await response.json().catch(
            () => null
          );

        throw new Error(
          errorData?.detail ||
          "Gmail sync failed"
        );
      }

      const data =
        await response.json();

      await loadEmails();

      alert(
        `Gmail sync completed.\n\n` +
        `Emails found: ${data.gmail_emails_found}\n` +
        `New emails: ${data.new_emails_saved}\n` +
        `Updated emails: ${data.existing_emails_updated}\n` +
        `Attachments: ${data.attachments_found}`
      );
    } catch (error) {
      console.error(
        "Gmail sync failed:",
        error
      );

      alert(
        error.message ||
        "Could not sync Gmail."
      );
    } finally {
      setSyncing(false);
    }
  };

  // =====================================================
  // SAVE RULE
  // =====================================================

  const handleSaveRule = async (event) => {
    event.preventDefault();

    if (!ruleValue.trim()) {
      return;
    }

    try {
      let response;

      if (editingRuleId !== null) {
        response = await fetch(
          `${API_URL}/api/rules/${editingRuleId}` +
            `?rule_type=${encodeURIComponent(
              ruleType
            )}` +
            `&rule_value=${encodeURIComponent(
              ruleValue.trim()
            )}`,
          {
            method: "PUT",
          }
        );
      } else {
        response = await fetch(
          `${API_URL}/api/rules` +
            `?rule_type=${encodeURIComponent(
              ruleType
            )}` +
            `&rule_value=${encodeURIComponent(
              ruleValue.trim()
            )}`,
          {
            method: "POST",
          }
        );
      }

      if (!response.ok) {
        throw new Error(
          "Failed to save rule"
        );
      }

      await loadRules();

      setEditingRuleId(null);
      setRuleValue("");
      setRuleType("keyword");
    } catch (error) {
      console.error(
        "Failed to save rule:",
        error
      );

      alert(
        "Could not save the rule."
      );
    }
  };

  // =====================================================
  // EDIT RULE
  // =====================================================

  const handleEditRule = (rule) => {
    setEditingRuleId(rule.id);
    setRuleType(rule.rule_type);
    setRuleValue(rule.rule_value);
  };

  // =====================================================
  // DELETE RULE
  // =====================================================

  const handleDeleteRule = async (id) => {
    try {
      const response = await fetch(
        `${API_URL}/api/rules/${id}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        throw new Error(
          "Failed to delete rule"
        );
      }

      await loadRules();

      if (editingRuleId === id) {
        setEditingRuleId(null);
        setRuleValue("");
        setRuleType("keyword");
      }
    } catch (error) {
      console.error(
        "Failed to delete rule:",
        error
      );

      alert(
        "Could not delete the rule."
      );
    }
  };

  // =====================================================
  // CANCEL RULE EDIT
  // =====================================================

  const cancelEdit = () => {
    setEditingRuleId(null);
    setRuleValue("");
    setRuleType("keyword");
  };

  // =====================================================
  // FORMAT DATE
  // =====================================================

  const formatDate = (date) => {
    if (!date) {
      return "";
    }

    try {
      return new Date(
        date
      ).toLocaleString();
    } catch {
      return date;
    }
  };

  // =====================================================
  // EMAIL BODY WITH CLICKABLE LINKS
  // =====================================================

  const renderEmailBody = (body) => {
    if (!body) {
      return "(No message body)";
    }

    const parts = body.split(
      /(https?:\/\/[^\s]+)/g
    );

    return parts.map(
      (part, index) => {
        if (
          part.startsWith(
            "http://"
          ) ||
          part.startsWith(
            "https://"
          )
        ) {
          return (
            <a
              key={index}
              href={part}
              target="_blank"
              rel="noreferrer"
            >
              {part}
            </a>
          );
        }

        return (
          <span key={index}>
            {part}
          </span>
        );
      }
    );
  };

  // =====================================================
  // UI
  // =====================================================

  return (
    <div className="app">

      {/* =================================================
          SIDEBAR
      ================================================= */}

      <aside className="sidebar">

        <h1>SmartMail</h1>

        <p className="sidebar-subtitle">
          Personalized Email
          Prioritization
        </p>

        <button
          className={
            activeSection === "all"
              ? "active"
              : ""
          }
          onClick={() =>
            setActiveSection("all")
          }
        >
          📥 All Mail
        </button>

        <button
          className={
            activeSection ===
            "important"
              ? "active"
              : ""
          }
          onClick={() =>
            setActiveSection(
              "important"
            )
          }
        >
          ⭐ Important
        </button>

        <button
          className={
            activeSection === "rules"
              ? "active"
              : ""
          }
          onClick={() =>
            setActiveSection("rules")
          }
        >
          ⚙️ Rules
        </button>

      </aside>

      {/* =================================================
          MAIN CONTENT
      ================================================= */}

      <main className="main-content">

        <header className="main-header">

          <div>

            <h2>
              {activeSection === "all"
                ? "All Mail"
                : activeSection ===
                  "important"
                ? "Important"
                : "Rules"}
            </h2>

            {activeSection === "all" && (
              <p>
                {emails.length} email
                {emails.length !== 1
                  ? "s"
                  : ""}
              </p>
            )}

            {activeSection ===
              "important" && (
              <p>
                {importantEmails.length}{" "}
                important email
                {importantEmails.length !==
                1
                  ? "s"
                  : ""}
              </p>
            )}

          </div>

          {/* =================================================
              GMAIL CONTROLS
          ================================================= */}

          {activeSection !==
            "rules" && (
            <div className="header-actions">

              <button
                className="connect-button"
                onClick={
                  handleConnectGmail
                }
              >
                🔗 Connect Gmail
              </button>

              <button
                className="sync-button"
                onClick={handleSync}
                disabled={syncing}
              >
                {syncing
                  ? "Syncing..."
                  : "↻ Sync Gmail"}
              </button>

            </div>
          )}

        </header>

        {/* =================================================
            RULES
        ================================================= */}

        {activeSection ===
          "rules" && (
          <section className="rules-card">

            <h3>
              {editingRuleId !== null
                ? "Edit Important Email Rule"
                : "Add Important Email Rule"}
            </h3>

            <form
              onSubmit={
                handleSaveRule
              }
            >

              <label>
                Rule Type
              </label>

              <select
                value={ruleType}
                onChange={(event) =>
                  setRuleType(
                    event.target.value
                  )
                }
              >

                <option value="keyword">
                  Keyword
                </option>

                <option value="sender">
                  Sender
                </option>

              </select>

              <label>
                Rule Value
              </label>

              <input
                type="text"
                value={ruleValue}
                onChange={(event) =>
                  setRuleValue(
                    event.target.value
                  )
                }
                placeholder={
                  ruleType ===
                  "keyword"
                    ? "Example: assignment"
                    : "Example: faculty"
                }
              />

              <div className="rule-form-buttons">

                <button
                  type="submit"
                  className="add-rule"
                >
                  {editingRuleId !==
                  null
                    ? "Update Rule"
                    : "Add Rule"}
                </button>

                {editingRuleId !==
                  null && (
                  <button
                    type="button"
                    className="cancel-button"
                    onClick={
                      cancelEdit
                    }
                  >
                    Cancel
                  </button>
                )}

              </div>

            </form>

            <hr />

            <h3>
              Your Rules
            </h3>

            {loadingRules ? (
              <p>
                Loading rules...
              </p>
            ) : rules.length === 0 ? (
              <p>
                No rules created yet.
              </p>
            ) : (
              <div className="rules-list">

                {rules.map((rule) => (
                  <div
                    className="rule-item"
                    key={rule.id}
                  >

                    <div>

                      <strong>
                        {rule.rule_type}
                      </strong>

                      <span>
                        {rule.rule_value}
                      </span>

                    </div>

                    <div className="rule-actions">

                      <button
                        onClick={() =>
                          handleEditRule(
                            rule
                          )
                        }
                      >
                        Edit
                      </button>

                      <button
                        onClick={() =>
                          handleDeleteRule(
                            rule.id
                          )
                        }
                      >
                        Delete
                      </button>

                    </div>

                  </div>
                ))}

              </div>
            )}

          </section>
        )}

        {/* =================================================
            EMAIL LIST
        ================================================= */}

        {activeSection !==
          "rules" && (
          <section className="email-list">

            {loadingEmails ? (
              <div className="empty-state">

                <p>
                  Loading your Gmail
                  emails...
                </p>

              </div>
            ) : displayedEmails.length ===
              0 ? (
              <div className="empty-state">

                <div className="empty-icon">
                  📭
                </div>

                <h3>
                  {activeSection ===
                  "important"
                    ? "No Important Emails"
                    : "No Emails"}
                </h3>

                <p>
                  {activeSection ===
                  "important"
                    ? "Create a rule to prioritize your emails."
                    : "Connect Gmail and sync to load your emails."}
                </p>

              </div>
            ) : (
              displayedEmails.map(
                (email) => {

                  const important =
                    isImportant(
                      email
                    );

                  return (
                    <div
                      className="email-card"
                      key={email.id}
                    >

                      {/* EMAIL HEADER */}

                      <div className="email-top">

                        <div className="sender-info">

                          <strong>
                            {email.sender}
                          </strong>

                          <span className="email-date">
                            {formatDate(
                              email.received_at
                            )}
                          </span>

                        </div>

                        {important && (
                          <span className="important-label">
                            ⭐ Important
                          </span>
                        )}

                      </div>

                      {/* SUBJECT */}

                      <h3>
                        {email.subject}
                      </h3>

                      {/* BODY */}

                      <div className="email-body">
                        {renderEmailBody(
                          email.body
                        )}
                      </div>

                      {/* ATTACHMENTS */}

                      {email.attachments &&
                        email.attachments
                          .length >
                          0 && (
                          <div className="attachments">

                            <h4>
                              Attachments
                            </h4>

                            {email.attachments.map(
                              (
                                attachment
                              ) => (
                                <a
                                  key={
                                    attachment.id
                                  }
                                  className="attachment"
                                  href={
                                    API_URL +
                                    attachment.download_url
                                  }
                                  target="_blank"
                                  rel="noreferrer"
                                >

                                  <span>
                                    📎
                                  </span>

                                  <span>
                                    {
                                      attachment.filename
                                    }
                                  </span>

                                </a>
                              )
                            )}

                          </div>
                        )}

                      {/* ORIGINAL GMAIL */}

                      {email.gmail_url && (
                        <div className="email-footer">

                          <a
                            href={
                              email.gmail_url
                            }
                            target="_blank"
                            rel="noreferrer"
                          >
                            Open in Gmail →
                          </a>

                        </div>
                      )}

                    </div>
                  );
                }
              )
            )}

          </section>
        )}

      </main>

    </div>
  );
}

export default App;