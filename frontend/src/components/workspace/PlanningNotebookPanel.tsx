import { useState, type FormEvent } from "react";

import type {
  NotebookCategory,
  NotebookPriority,
  PlanningNotebookFocus,
  PlanningNotebookItem,
  PlanningNotebookState,
} from "../../api/workspace";

const NOTEBOOK_CATEGORIES: { value: NotebookCategory; label: string }[] = [
  { value: "route", label: "Route" },
  { value: "lodging", label: "Lodging" },
  { value: "activities", label: "Activities" },
  { value: "budget", label: "Budget" },
  { value: "documents", label: "Documents" },
  { value: "policy", label: "Policy" },
  { value: "other", label: "Other" },
];

function categoryLabel(category: NotebookCategory): string {
  return NOTEBOOK_CATEGORIES.find((c) => c.value === category)?.label ?? category;
}

function priorityLabel(priority: NotebookPriority): string {
  if (priority === "high") return "High";
  if (priority === "low") return "Low";
  return "";
}

function NotebookItemCard({
  item,
  isFocused,
  busyItemId,
  onComplete,
  onReopen,
  onDelete,
  onFocus,
}: {
  item: PlanningNotebookItem;
  isFocused: boolean;
  busyItemId: string | null;
  onComplete: (id: string) => void;
  onReopen: (id: string) => void;
  onDelete: (id: string) => void;
  onFocus: (id: string) => void;
}) {
  const isBusy = busyItemId === item.notebook_item_id;

  return (
    <article
      className={`notebook-item-card${isFocused ? " notebook-item-card-focused" : ""}${item.status === "completed" ? " notebook-item-card-completed" : ""}`}
      aria-label={item.title}
    >
      <div className="notebook-item-header">
        <span className="notebook-item-category">{categoryLabel(item.category)}</span>
        {item.priority === "high" ? (
          <span className="notebook-item-priority">{priorityLabel(item.priority)}</span>
        ) : null}
        {isFocused ? <span className="notebook-item-focus-pill">Active focus</span> : null}
      </div>
      <h3 className="notebook-item-title">{item.title}</h3>
      {item.note ? <p className="notebook-item-note muted-copy">{item.note}</p> : null}
      <div className="notebook-item-actions">
        {item.status === "active" ? (
          <>
            <button
              type="button"
              className="notebook-action-button"
              disabled={isBusy}
              onClick={() => onComplete(item.notebook_item_id)}
            >
              Complete
            </button>
            <button
              type="button"
              className={`notebook-action-button${isFocused ? " notebook-action-button-active" : ""}`}
              disabled={isBusy}
              onClick={() => onFocus(item.notebook_item_id)}
            >
              {isFocused ? "Focused" : "Focus"}
            </button>
          </>
        ) : (
          <button
            type="button"
            className="notebook-action-button"
            disabled={isBusy}
            onClick={() => onReopen(item.notebook_item_id)}
          >
            Reopen
          </button>
        )}
        <button
          type="button"
          className="notebook-action-button notebook-action-button-delete"
          disabled={isBusy}
          onClick={() => onDelete(item.notebook_item_id)}
        >
          Delete
        </button>
      </div>
    </article>
  );
}

export function PlanningNotebookPanel({
  notebookState,
  busyLabel,
  successMessage,
  errorMessage,
  onCreateItem,
  onCompleteItem,
  onReopenItem,
  onDeleteItem,
  onSetFocus,
}: {
  notebookState: PlanningNotebookState;
  busyLabel: string | null;
  successMessage?: string | null;
  errorMessage: string | null;
  onCreateItem: (payload: { title: string; category: NotebookCategory; note?: string; priority?: NotebookPriority }) => Promise<void>;
  onCompleteItem: (notebookItemId: string) => Promise<void>;
  onReopenItem: (notebookItemId: string) => Promise<void>;
  onDeleteItem: (notebookItemId: string) => Promise<void>;
  onSetFocus: (focus: { category?: NotebookCategory | null; notebook_item_id?: string | null }) => Promise<void>;
}) {
  const [captureTitle, setCaptureTitle] = useState("");
  const [captureCategory, setCaptureCategory] = useState<NotebookCategory>("other");
  const [captureNote, setCaptureNote] = useState("");
  const [capturePriority, setCapturePriority] = useState<NotebookPriority>("normal");
  const [validationMessage, setValidationMessage] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<NotebookCategory | "all">("all");
  const [showCompleted, setShowCompleted] = useState(false);
  const [busyItemId, setBusyItemId] = useState<string | null>(null);

  const { summary, focus } = notebookState;

  const filteredActive =
    activeFilter === "all"
      ? summary.active_items
      : summary.active_items.filter((item) => item.category === activeFilter);

  const focusedItemId = focus.notebook_item_id;

  async function handleCaptureSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidationMessage(null);

    if (captureTitle.trim().length === 0) {
      setValidationMessage("Enter a title before adding a notebook item.");
      return;
    }

    await onCreateItem({
      title: captureTitle.trim(),
      category: captureCategory,
      note: captureNote.trim() || undefined,
      priority: capturePriority === "normal" ? undefined : capturePriority,
    });

    setCaptureTitle("");
    setCaptureNote("");
    setCapturePriority("normal");
  }

  async function handleComplete(notebookItemId: string) {
    setBusyItemId(notebookItemId);
    try {
      await onCompleteItem(notebookItemId);
    } finally {
      setBusyItemId(null);
    }
  }

  async function handleReopen(notebookItemId: string) {
    setBusyItemId(notebookItemId);
    try {
      await onReopenItem(notebookItemId);
    } finally {
      setBusyItemId(null);
    }
  }

  async function handleDelete(notebookItemId: string) {
    setBusyItemId(notebookItemId);
    try {
      await onDeleteItem(notebookItemId);
    } finally {
      setBusyItemId(null);
    }
  }

  async function handleFocusItem(notebookItemId: string) {
    const alreadyFocused = focusedItemId === notebookItemId;
    await onSetFocus({
      notebook_item_id: alreadyFocused ? null : notebookItemId,
      category: alreadyFocused ? null : undefined,
    });
  }

  async function handleFocusCategory(category: NotebookCategory | null) {
    await onSetFocus({ category, notebook_item_id: null });
  }

  const activeCategoryFilter = NOTEBOOK_CATEGORIES.filter((cat) =>
    summary.active_items.some((item) => item.category === cat.value)
  );

  return (
    <section className="status-card planning-notebook-card" aria-label="Planning notebook">
      <p className="status-label">Notebook</p>
      <h2>Planning notebook</h2>
      <p className="muted-copy">
        Capture notes, reminders, and follow-ups by category. Active items stay visible while
        completed items are archived for later review.
      </p>

      {focus.category || focus.notebook_item_id ? (
        <div className="notebook-focus-banner" aria-label="Active notebook focus">
          <span className="notebook-focus-label">Active focus:</span>
          <span className="notebook-focus-value">
            {focus.notebook_item_id
              ? (notebookState.items.find((i) => i.notebook_item_id === focus.notebook_item_id)?.title ?? focus.notebook_item_id)
              : focus.category
                ? categoryLabel(focus.category)
                : null}
          </span>
          <button
            type="button"
            className="notebook-action-button"
            onClick={() => handleFocusCategory(null)}
          >
            Clear focus
          </button>
        </div>
      ) : null}

      {busyLabel ? <p className="muted-copy">{busyLabel}</p> : null}
      {successMessage ? (
        <p className="planner-inline-success" role="status">
          {successMessage}
        </p>
      ) : null}
      {errorMessage ? <p className="planner-inline-error">{errorMessage}</p> : null}
      {validationMessage ? <p className="planner-inline-error">{validationMessage}</p> : null}

      <form className="notebook-capture-form" onSubmit={handleCaptureSubmit}>
        <label className="notebook-capture-title-field">
          <span>Quick capture</span>
          <input
            aria-label="Notebook item title"
            placeholder="Add a note, reminder, or follow-up..."
            value={captureTitle}
            onChange={(event) => setCaptureTitle(event.target.value)}
          />
        </label>
        <div className="notebook-capture-row">
          <label className="notebook-field">
            <span>Category</span>
            <select
              aria-label="Notebook category"
              value={captureCategory}
              onChange={(event) => setCaptureCategory(event.target.value as NotebookCategory)}
            >
              {NOTEBOOK_CATEGORIES.map((cat) => (
                <option key={cat.value} value={cat.value}>
                  {cat.label}
                </option>
              ))}
            </select>
          </label>
          <label className="notebook-field">
            <span>Priority</span>
            <select
              aria-label="Notebook priority"
              value={capturePriority}
              onChange={(event) => setCapturePriority(event.target.value as NotebookPriority)}
            >
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
            </select>
          </label>
        </div>
        <label className="notebook-capture-title-field">
          <span>Note (optional)</span>
          <input
            aria-label="Notebook item note"
            placeholder="Optional detail..."
            value={captureNote}
            onChange={(event) => setCaptureNote(event.target.value)}
          />
        </label>
        <button
          type="submit"
          className="budget-action-button"
          disabled={Boolean(busyLabel)}
        >
          Add to notebook
        </button>
      </form>

      {activeCategoryFilter.length > 0 ? (
        <div className="notebook-category-filters" role="group" aria-label="Category filters">
          <button
            type="button"
            className={`notebook-filter-button${activeFilter === "all" ? " notebook-filter-button-active" : ""}`}
            onClick={() => setActiveFilter("all")}
          >
            All ({summary.active_count})
          </button>
          {activeCategoryFilter.map((cat) => {
            const count = summary.active_items.filter((i) => i.category === cat.value).length;
            return (
              <button
                key={cat.value}
                type="button"
                className={`notebook-filter-button${activeFilter === cat.value ? " notebook-filter-button-active" : ""}${focus.category === cat.value ? " notebook-filter-button-focused" : ""}`}
                onClick={() => {
                  setActiveFilter(cat.value);
                  handleFocusCategory(focus.category === cat.value ? null : cat.value);
                }}
              >
                {cat.label} ({count})
              </button>
            );
          })}
        </div>
      ) : null}

      {filteredActive.length === 0 ? (
        <p className="muted-copy">
          {summary.active_count === 0
            ? "No notebook items yet. Use quick capture above to add your first note."
            : "No active items in this category."}
        </p>
      ) : (
        <div className="notebook-item-list" aria-label="Active notebook items">
          {filteredActive.map((item) => (
            <NotebookItemCard
              key={item.notebook_item_id}
              item={item}
              isFocused={focusedItemId === item.notebook_item_id}
              busyItemId={busyItemId}
              onComplete={handleComplete}
              onReopen={handleReopen}
              onDelete={handleDelete}
              onFocus={handleFocusItem}
            />
          ))}
        </div>
      )}

      {summary.completed_count > 0 ? (
        <details
          className="notebook-completed-section"
          open={showCompleted}
          onToggle={(event) => setShowCompleted((event.target as HTMLDetailsElement).open)}
        >
          <summary className="notebook-completed-summary">
            Completed ({summary.completed_count})
          </summary>
          <div className="notebook-item-list" aria-label="Completed notebook items">
            {summary.completed_items.map((item) => (
              <NotebookItemCard
                key={item.notebook_item_id}
                item={item}
                isFocused={false}
                busyItemId={busyItemId}
                onComplete={handleComplete}
                onReopen={handleReopen}
                onDelete={handleDelete}
                onFocus={handleFocusItem}
              />
            ))}
          </div>
        </details>
      ) : null}
    </section>
  );
}
