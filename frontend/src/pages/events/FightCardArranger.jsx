import { useEffect, useState } from 'react'
import {
  DndContext, KeyboardSensor, PointerSensor, closestCenter,
  useSensor, useSensors,
} from '@dnd-kit/core'
import {
  SortableContext, arrayMove, sortableKeyboardCoordinates,
  useSortable, verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

/**
 * Drag-and-drop running order for a full fight card.
 *
 * The list reads top to bottom as the card is billed — main event first — but
 * that is the *last* fight of the night, so each row states its billing and
 * its running position explicitly. Leaving that implicit is how a card ends up
 * built upside down.
 */
export default function FightCardArranger({ bouts, onSave, saving }) {
  const [order, setOrder] = useState(bouts)
  const [dirty, setDirty] = useState(false)

  // Re-sync when the server sends a new card, but never while the user has
  // unsaved changes — that would silently discard their arrangement.
  useEffect(() => {
    if (!dirty) setOrder(bouts)
  }, [bouts, dirty])

  const sensors = useSensors(
    // A small distance threshold so a tap that scrolls the page on a phone is
    // not interpreted as the start of a drag.
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  function handleDragEnd({ active, over }) {
    if (!over || active.id === over.id) return
    setOrder(items => {
      const from = items.findIndex(b => b.id === active.id)
      const to   = items.findIndex(b => b.id === over.id)
      return arrayMove(items, from, to)
    })
    setDirty(true)
  }

  // Keyboard and touch users need a way through that is not dragging.
  function move(index, delta) {
    const to = index + delta
    if (to < 0 || to >= order.length) return
    setOrder(items => arrayMove(items, index, to))
    setDirty(true)
  }

  return (
    <>
      <p className="card-hint">
        Drag to set the running order, or use the arrows. The <strong>main
        event</strong> sits at the top of the card and is fought last; the
        opener is at the bottom and goes on first.
      </p>

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={order.map(b => b.id)} strategy={verticalListSortingStrategy}>
          {order.map((bout, i) => (
            <SortableBout
              key={bout.id}
              bout={bout}
              billing={billingFor(i, order.length)}
              position={order.length - i}
              total={order.length}
              onUp={() => move(i, -1)}
              onDown={() => move(i, 1)}
              isFirst={i === 0}
              isLast={i === order.length - 1}
            />
          ))}
        </SortableContext>
      </DndContext>

      <div className="btn-row" style={{ marginTop: '1rem' }}>
        <button className="btn btn-primary btn-sm" disabled={!dirty || saving}
          onClick={() => onSave(order.map(b => b.id), () => setDirty(false))}>
          {saving ? 'Saving…' : 'Save running order'}
        </button>
        {dirty && (
          <button className="btn btn-sm" disabled={saving}
            onClick={() => { setOrder(bouts); setDirty(false) }}>
            Discard changes
          </button>
        )}
      </div>
    </>
  )
}

/** Cards are billed in tiers, and the names are the ones promoters use. */
function billingFor(index, total) {
  if (index === 0) return 'Main event'
  if (index === 1) return 'Co-main'
  if (index >= total - 1) return 'Opening bout'
  return index < 4 ? 'Main card' : 'Prelim'
}

function SortableBout({ bout, billing, position, total, onUp, onDown, isFirst, isLast }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: bout.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
    zIndex: isDragging ? 2 : undefined,
  }

  const a = bout.fighter_a?.name ?? 'TBC'
  const b = bout.fighter_b?.name ?? 'TBC'

  return (
    <div ref={setNodeRef} style={style}
      className={`card-row${isFirst ? ' card-row--main' : ''}`}>
      <button className="card-grip" {...attributes} {...listeners}
        aria-label={`Reorder ${a} vs ${b}`} title="Drag to reorder">⠿</button>

      <div className="card-row-body">
        <div className="card-row-billing">
          <span className={`billing-pill${isFirst ? ' billing-pill--main' : ''}`}>{billing}</span>
          {/* Running position, counted the way the night actually unfolds. */}
          <span className="card-row-order">Fight {position} of {total}</span>
        </div>
        <div className="card-row-names">{a} <span className="vs">vs</span> {b}</div>
        <div className="card-row-meta">
          {bout.sport}{bout.ruleset ? ` · ${bout.ruleset}` : ''}
          {bout.completed ? ' · Result recorded' : ''}
        </div>
      </div>

      <div className="card-row-moves">
        <button className="move-btn" onClick={onUp} disabled={isFirst}
          aria-label="Move up the card">↑</button>
        <button className="move-btn" onClick={onDown} disabled={isLast}
          aria-label="Move down the card">↓</button>
      </div>
    </div>
  )
}
