import './ConfirmModal.css';

interface ConfirmModalProps {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'warning' | 'default';
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
  error?: string;
}

export default function ConfirmModal({
  title,
  message,
  confirmText = 'CONFIRM',
  cancelText = 'CANCEL',
  variant = 'default',
  onConfirm,
  onCancel,
  isLoading = false,
  error,
}: ConfirmModalProps) {
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-content confirm-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className={`modal-title ${variant === 'danger' ? 'text-red' : ''}`}>
            {title}
          </h3>
          <button className="modal-close" onClick={onCancel}>
            &times;
          </button>
        </div>

        {error && (
          <div className="alert alert-error mb-md">
            [ERROR] {error}
          </div>
        )}

        <div className="confirm-message">
          <p>{message}</p>
        </div>

        <div className="flex gap-md justify-end mt-lg">
          <button
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={isLoading}
          >
            {cancelText}
          </button>
          <button
            className={`btn ${variant === 'danger' ? 'btn-danger' : 'btn-primary'}`}
            onClick={onConfirm}
            disabled={isLoading}
          >
            {isLoading ? 'PROCESSING...' : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
