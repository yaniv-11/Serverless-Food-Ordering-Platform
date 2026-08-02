export default function MenuItemCard({ item, onAdd }) {
  return (
    <div className="menu-item-card">
      <img src={item.image_url} alt={item.name} />
      <div className="menu-item-body">
        <h4>
          <span className={`veg-dot ${item.is_veg ? "veg" : "non-veg"}`} />
          {item.name}
        </h4>
        <p className="muted">{item.description}</p>
        <div className="menu-item-footer">
          <span className="price">₹{item.price}</span>
          <button className="btn btn-outline" onClick={() => onAdd(item)}>
            Add
          </button>
        </div>
      </div>
    </div>
  );
}
