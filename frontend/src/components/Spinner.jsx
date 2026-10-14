export default function Spinner({ full }) {
  if (full) return (
    <div className="spinner-full">
      <div className="spinner" />
    </div>
  )
  return <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem 0' }}><div className="spinner" /></div>
}
