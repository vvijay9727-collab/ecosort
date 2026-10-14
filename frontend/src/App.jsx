import { useEffect, useRef, useState } from 'react'
import './App.css'

const iconPaths = {
  arrow: <path d="M5 12h14m-7-7 7 7-7 7" />,
  camera: (
    <>
      <path d="M14 5H9L7 8H4a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2h-3l-3-3Z" />
      <circle cx="12" cy="14" r="3" />
    </>
  ),
  chart: (
    <>
      <path d="M3 3v18h18" />
      <path d="m19 9-5 5-4-4-5 5" />
    </>
  ),
  check: <path d="m5 12 4 4L19 6" />,
  leaf: (
    <>
      <path d="M20 4c-8 0-14 3-14 10a6 6 0 0 0 6 6c7 0 10-6 8-16Z" />
      <path d="M4 20c3-5 6-8 11-11" />
    </>
  ),
  location: (
    <>
      <path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z" />
      <circle cx="12" cy="10" r="2.5" />
    </>
  ),
  recycle: (
    <>
      <path d="m7 7 2-3 3 1" />
      <path d="m9 4 2 4H6" />
      <path d="m17 7 3 1v4" />
      <path d="m20 8-4 2 2 3" />
      <path d="m15 19-3 1-3-2" />
      <path d="m12 20 1-4 4 2" />
    </>
  ),
  shield: (
    <>
      <path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  sparkle: (
    <>
      <path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3Z" />
      <path d="m19 14 1.2 2.8L23 18l-2.8 1.2L19 22l-1.2-2.8L15 18l2.8-1.2L19 14Z" />
    </>
  ),
}

function Icon({ name, className = '' }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.7"
    >
      {iconPaths[name]}
    </svg>
  )
}

function Brand({ footer = false }) {
  return (
    <a
      className={`brand${footer ? ' brand--footer' : ''}`}
      href={window.location.pathname === '/' ? '#home' : '/'}
      aria-label="EcoSort home"
    >
      <span className="brand-mark">
        <Icon name="leaf" />
      </span>
      <span>eco<span className="brand-accent">sort</span></span>
    </a>
  )
}

function Navbar({ user = null }) {
  async function logout() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      })
      if (!response.ok) {
        throw new Error(`Logout failed (HTTP ${response.status}).`)
      }
    } catch (error) {
      window.alert(error.message || 'Could not sign out. Please try again.')
      return
    }
    window.location.href = '/'
  }

  return (
    <header className="site-header">
      <nav className="nav container" aria-label="Main navigation">
        <Brand />
        {user ? (
          <>
            <a className="nav-login-link" href={user.role === 'authority' ? '/authority/dashboard' : '/user/dashboard'}>
              Dashboard
            </a>
            <span className="nav-user">Signed in as {user.full_name}</span>
            <button className="nav-cta" type="button" onClick={logout}>Log out</button>
          </>
        ) : (
          <>
            <div className="nav-links">
              <a href="#home">Home</a>
              <a href="#services">Our services</a>
              <a href="#how-it-works">How it works</a>
            </div>
            <div className="nav-auth-links">
              <a className="nav-login-link" href="/user/login">User Login</a>
              <a className="nav-cta" href="/authority/login">Municipal Authority Login</a>
            </div>
          </>
        )}
      </nav>
    </header>
  )
}

function Hero() {
  return (
    <section className="hero container" id="home">
      <div className="hero-copy">
        <span className="eyebrow"><span className="eyebrow-dot" /> A cleaner tomorrow starts here</span>
        <h1>Small actions.<br /><span>Greener</span> communities.</h1>
        <p className="hero-description">
          Make waste management smarter. Sort waste with AI, report local issues,
          and help make your neighborhood a cleaner place to live.
        </p>
        <div className="hero-actions">
          <a className="button button--primary" href="/user/login">
            User Login <Icon name="arrow" />
          </a>
          <a className="text-link" href="/authority/login">Municipal Authority Login <span>→</span></a>
        </div>
        <div className="community-proof">
          <div className="proof-avatars" aria-hidden="true">
            <span>R</span><span>A</span><span>M</span><span>+</span>
          </div>
          <p><strong>Join your community</strong><br />working toward cleaner streets</p>
        </div>
      </div>

      <div className="hero-art" aria-label="Illustration of a greener neighborhood">
        <div className="art-sun" />
        <div className="art-orbit art-orbit--one" />
        <div className="art-orbit art-orbit--two" />
        <div className="floating-label floating-label--top"><span>✳</span> Make it count</div>
        <div className="landscape">
          <div className="hill hill--back" />
          <div className="hill hill--front" />
          <div className="art-tree art-tree--one"><i /><b /></div>
          <div className="art-tree art-tree--two"><i /><b /></div>
          <div className="art-tree art-tree--three"><i /><b /></div>
          <div className="art-bin"><div /><span>♻</span></div>
          <div className="pathway" />
        </div>
        <div className="floating-label floating-label--bottom"><Icon name="location" /> Better starts locally</div>
      </div>
    </section>
  )
}

function RoleSelection() {
  return (
    <section className="role-selection container" aria-labelledby="role-selection-title">
      <div className="role-selection-heading">
        <span className="eyebrow">Welcome to EcoSort</span>
        <h2 id="role-selection-title">Choose your workspace</h2>
        <p>Sign in to report neighborhood waste or manage municipal cleanup requests.</p>
      </div>
      <div className="role-option-grid">
        <article className="role-option-card">
          <span className="role-option-icon"><Icon name="leaf" /></span>
          <h3>For residents</h3>
          <p>Submit waste reports, see AI classifications, and follow your complaint progress.</p>
          <div>
            <a className="button button--primary" href="/user/login">User Login <Icon name="arrow" /></a>
            <a className="text-link" href="/user/register">Create a user account</a>
          </div>
        </article>
        <article className="role-option-card role-option-card--authority">
          <span className="role-option-icon"><Icon name="shield" /></span>
          <h3>For municipal authorities</h3>
          <p>Review reports, assign departments, update statuses, and document completed cleanup.</p>
          <div>
            <a className="button button--primary" href="/authority/login">Municipal Authority Login <Icon name="arrow" /></a>
            <small>Accounts are provisioned by an administrator.</small>
          </div>
        </article>
      </div>
    </section>
  )
}

function ActionCard({ icon, label, title, description, button, href, variant }) {
  return (
    <article className={`action-card action-card--${variant}`}>
      <div className="action-card-top">
        <span className="action-icon"><Icon name={icon} /></span>
        <span className="card-label">{label}</span>
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      <a className={`button ${variant === 'ai' ? 'button--primary' : 'button--light'}`} href={href}>
        {button}<Icon name="arrow" />
      </a>
      {variant === 'ai' && <div className="card-decoration" aria-hidden="true">✳</div>}
    </article>
  )
}

const MAX_IMAGE_SIZE = 10 * 1024 * 1024
const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

function WasteClassifier() {
  const inputRef = useRef(null)
  const [image, setImage] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [prediction, setPrediction] = useState('')
  const previewUrl = image?.url ?? ''

  useEffect(() => {
    return () => {
      if (image?.url) URL.revokeObjectURL(image.url)
    }
  }, [image])

  function selectImage(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    setError('')
    setPrediction('')

    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      setImage(null)
      setError('Choose a JPEG, PNG, or WebP image.')
      return
    }

    if (file.size > MAX_IMAGE_SIZE) {
      setImage(null)
      setError('The image must be 10 MB or smaller.')
      return
    }

    setImage({ file, url: URL.createObjectURL(file) })
  }

  function removeImage() {
    setImage(null)
    setPrediction('')
    setError('')
    if (inputRef.current) inputRef.current.value = ''
  }

  async function classifyImage() {
    if (!image || loading) return

    setLoading(true)
    setError('')
    setPrediction('')

    const formData = new FormData()
    formData.append('photo', image.file)
    try {
      const response = await fetch(`${API_BASE_URL}/api/classify`, {
        method: 'POST',
        body: formData,
      })
      const result = await response.json()
      if (!response.ok) {
        const detail = Array.isArray(result.detail)
          ? result.detail.map((issue) => issue.msg).join(' ')
          : result.detail
        throw new Error(detail || `Classification failed (HTTP ${response.status}).`)
      }
      setPrediction(result)
    } catch (error) {
      setError(
        error instanceof TypeError
          ? `Could not connect to the local API at ${API_BASE_URL}. Make sure the FastAPI server and trained model are available.`
          : error.message || 'The image could not be classified. Please try again.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="classifier-section" id="waste-classifier">
      <div className="classifier-container container">
        <div className="classifier-heading">
          <span className="eyebrow">AI waste classification</span>
          <h2>What goes where?</h2>
          <p>Choose a waste image to try the classification interface.</p>
        </div>
        <div className="classifier-panel">
          <div className="classifier-upload">
            {!image ? (
              <button
                className="upload-dropzone"
                type="button"
                onClick={() => inputRef.current?.click()}
                aria-describedby="upload-guidance"
              >
                <span className="upload-icon"><Icon name="camera" /></span>
                <strong>Select a waste image</strong>
                <span>Browse your device to upload a photo</span>
                <span className="upload-filetypes" id="upload-guidance">JPEG, PNG, or WebP · up to 10 MB</span>
              </button>
            ) : (
              <div className="image-preview">
                <img src={previewUrl} alt={`Selected waste: ${image.file.name}`} />
                <div className="preview-actions">
                  <span className="preview-filename" title={image.file.name}>{image.file.name}</span>
                  <button type="button" onClick={() => inputRef.current?.click()}>Replace</button>
                  <button type="button" onClick={removeImage}>Remove</button>
                </div>
              </div>
            )}
            <input
              ref={inputRef}
              className="visually-hidden"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={selectImage}
              aria-label="Select a waste image"
            />
          </div>
          <div className="classifier-controls">
            <div className="classifier-note">
              <Icon name="sparkle" />
              <p><strong>Trained image model</strong><br />Predictions are generated by EcoSort’s local classifier.</p>
            </div>
            <button
              className="button button--primary classify-button"
              type="button"
              onClick={classifyImage}
              disabled={!image || loading}
            >
              {loading ? <><span className="loading-spinner" /> Classifying image…</> : 'Classify Waste'}
              {!loading && <Icon name="arrow" />}
            </button>
            {error && <p className="classifier-message classifier-message--error" role="alert">{error}</p>}
            {prediction && (
              <div className="prediction-result" role="status">
                <span className="model-badge">MODEL PREDICTION</span>
                <strong>Category: {prediction.category}</strong>
                <p>
                  Confidence: {(prediction.confidence * 100).toFixed(1)}%
                  {prediction.model_version ? ` · ${prediction.model_version}` : ''}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}

function ReportImagePicker({ image, previewUrl, error, onSelect, onRemove, inputRef }) {
  return (
    <div className="report-image-field">
      <span className="form-label">Photo <span aria-hidden="true">*</span></span>
      {!image ? (
        <button
          className="upload-dropzone report-dropzone"
          type="button"
          onClick={() => inputRef.current?.click()}
          aria-describedby="report-photo-guidance"
          aria-invalid={Boolean(error)}
        >
          <span className="upload-icon"><Icon name="camera" /></span>
          <strong>Add a photo of the issue</strong>
          <span>Choose a clear image of the garbage</span>
          <span className="upload-filetypes" id="report-photo-guidance">JPEG, PNG, or WebP · up to 10 MB</span>
        </button>
      ) : (
        <div className="image-preview report-image-preview">
          <img src={previewUrl} alt={`Garbage report photo: ${image.name}`} />
          <div className="preview-actions">
            <span className="preview-filename" title={image.name}>{image.name}</span>
            <button type="button" onClick={() => inputRef.current?.click()}>Replace</button>
            <button type="button" onClick={onRemove}>Remove</button>
          </div>
        </div>
      )}
      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={onSelect}
        aria-label="Upload a photo of the garbage"
      />
      {error && <p className="field-error" role="alert">{error}</p>}
    </div>
  )
}

function ReportLocationFields({ mode, onModeChange, address, onAddressChange, latitude, onLatitudeChange, longitude, onLongitudeChange, errors }) {
  return (
    <fieldset className="location-fieldset">
      <legend className="form-label">Location <span aria-hidden="true">*</span></legend>
      <div className="location-mode" role="group" aria-label="Choose location format">
        <button
          type="button"
          className={mode === 'address' ? 'location-mode-button is-selected' : 'location-mode-button'}
          onClick={() => onModeChange('address')}
          aria-pressed={mode === 'address'}
        >
          Address or landmark
        </button>
        <button
          type="button"
          className={mode === 'coordinates' ? 'location-mode-button is-selected' : 'location-mode-button'}
          onClick={() => onModeChange('coordinates')}
          aria-pressed={mode === 'coordinates'}
        >
          Latitude / longitude
        </button>
      </div>
      {mode === 'address' ? (
        <>
          <label className="visually-hidden" htmlFor="report-address">Address or landmark</label>
          <input
            id="report-address"
            className={`form-input${errors.location ? ' has-error' : ''}`}
            type="text"
            placeholder="Street, area, or nearby landmark"
            value={address}
            onChange={(event) => onAddressChange(event.target.value)}
            aria-invalid={Boolean(errors.location)}
            aria-describedby={errors.location ? 'report-location-error' : undefined}
          />
        </>
      ) : (
        <div className="coordinate-inputs">
          <label className="coordinate-field" htmlFor="report-latitude">
            <span>Latitude</span>
            <input
              id="report-latitude"
              className={`form-input${errors.location ? ' has-error' : ''}`}
              type="number"
              min="-90"
              max="90"
              step="any"
              placeholder="e.g. 12.9716"
              value={latitude}
              onChange={(event) => onLatitudeChange(event.target.value)}
              aria-invalid={Boolean(errors.location)}
            />
          </label>
          <label className="coordinate-field" htmlFor="report-longitude">
            <span>Longitude</span>
            <input
              id="report-longitude"
              className={`form-input${errors.location ? ' has-error' : ''}`}
              type="number"
              min="-180"
              max="180"
              step="any"
              placeholder="e.g. 77.5946"
              value={longitude}
              onChange={(event) => onLongitudeChange(event.target.value)}
              aria-invalid={Boolean(errors.location)}
            />
          </label>
        </div>
      )}
      {errors.location && <p className="field-error" id="report-location-error" role="alert">{errors.location}</p>}
    </fieldset>
  )
}

function GarbageReportForm() {
  const imageInputRef = useRef(null)
  const idempotencyKeyRef = useRef(null)
  const [image, setImage] = useState(null)
  const [description, setDescription] = useState('')
  const [locationMode, setLocationMode] = useState('address')
  const [address, setAddress] = useState('')
  const [latitude, setLatitude] = useState('')
  const [longitude, setLongitude] = useState('')
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState('')
  const [submissionError, setSubmissionError] = useState('')
  const [reports, setReports] = useState([])
  const [reportCount, setReportCount] = useState(0)
  const [reportsLoading, setReportsLoading] = useState(true)
  const [reportsError, setReportsError] = useState('')
  const previewUrl = image?.url ?? ''

  useEffect(() => {
    const controller = new AbortController()

    async function loadReports() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/reports`, {
          credentials: 'include',
          signal: controller.signal,
        })
        const result = await response.json()
        if (!response.ok) {
          const detail = Array.isArray(result.detail)
            ? result.detail.map((issue) => issue.msg).join(' ')
            : result.detail
          throw new Error(detail || `Reports could not be loaded (HTTP ${response.status}).`)
        }
        setReports(result)
        setReportCount(result.length)
        setReportsError('')
      } catch (error) {
        if (error.name !== 'AbortError') {
          setReportsError(
            error instanceof TypeError
              ? `Could not connect to the local API at ${API_BASE_URL}.`
              : error.message || 'Recent reports could not be loaded.',
          )
        }
      } finally {
        if (!controller.signal.aborted) setReportsLoading(false)
      }
    }

    loadReports()
    return () => controller.abort()
  }, [])

  useEffect(() => {
    return () => {
      if (image?.url) URL.revokeObjectURL(image.url)
    }
  }, [image])

  function selectReportImage(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    setMessage('')
    idempotencyKeyRef.current = null
    setErrors((current) => ({ ...current, image: '' }))
    setSubmissionError('')
    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      setImage(null)
      setErrors((current) => ({ ...current, image: 'Choose a JPEG, PNG, or WebP image.' }))
      return
    }
    if (file.size > MAX_IMAGE_SIZE) {
      setImage(null)
      setErrors((current) => ({ ...current, image: 'The photo must be 10 MB or smaller.' }))
      return
    }

    setImage({ file, url: URL.createObjectURL(file) })
  }

  function removeReportImage() {
    setImage(null)
    idempotencyKeyRef.current = null
    setErrors((current) => ({ ...current, image: '' }))
    setMessage('')
    setSubmissionError('')
    if (imageInputRef.current) imageInputRef.current.value = ''
  }

  async function submitReport(event) {
    event.preventDefault()
    if (submitting) return

    const nextErrors = {}
    if (!image) nextErrors.image = 'Add a photo before submitting.'
    if (!description.trim()) nextErrors.description = 'Enter a description of the garbage.'

    if (locationMode === 'address') {
      if (!address.trim()) nextErrors.location = 'Enter an address or nearby landmark.'
    } else {
      const lat = latitude.trim() === '' ? Number.NaN : Number(latitude)
      const lon = longitude.trim() === '' ? Number.NaN : Number(longitude)
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        nextErrors.location = 'Enter both latitude and longitude.'
      } else if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
        nextErrors.location = 'Latitude must be between -90 and 90, and longitude between -180 and 180.'
      }
    }

    setErrors(nextErrors)
    setMessage('')
    setSubmissionError('')
    if (Object.keys(nextErrors).length > 0) return

    setSubmitting(true)
    const formData = new FormData()
    formData.append('description', description.trim())
    formData.append('photo', image.file)
    if (locationMode === 'address') {
      formData.append('location', address.trim())
    } else {
      formData.append('latitude', latitude)
      formData.append('longitude', longitude)
    }

    try {
      idempotencyKeyRef.current ??= crypto.randomUUID()
      const response = await fetch(`${API_BASE_URL}/api/reports`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Idempotency-Key': idempotencyKeyRef.current },
        body: formData,
      })
      const result = await response.json()

      if (!response.ok) {
        const detail = Array.isArray(result.detail)
          ? result.detail.map((issue) => issue.msg).join(' ')
          : result.detail
        throw new Error(detail || `Report submission failed (HTTP ${response.status}).`)
      }

      const confidence = (result.prediction_confidence * 100).toFixed(1)
      setMessage(
        `Report #${result.id} created complaint #${result.complaint_id}, assigned to ${result.assigned_department} at ${result.location || `coordinates ${result.latitude}, ${result.longitude}`}. ${result.predicted_category} (${confidence}% confidence); complaint status: ${result.complaint_status}.`,
      )
      setReports((current) => [result, ...current.filter((report) => report.id !== result.id)])
      if (response.status === 201) setReportCount((current) => current + 1)
      setReportsError('')
      idempotencyKeyRef.current = null
    } catch (error) {
      setSubmissionError(
        error instanceof TypeError
          ? `Could not connect to the local API at ${API_BASE_URL}. Make sure the FastAPI server is running.`
          : error.message || 'The report could not be submitted. Please try again.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="report-section" id="garbage-report">
      <div className="report-container container">
        <div className="classifier-heading">
          <span className="eyebrow">Community care</span>
          <h2>Report garbage nearby</h2>
          <p>Share a photo and location to submit a report to the local API.</p>
        </div>
        <form className="report-panel" onSubmit={submitReport} noValidate>
          <ReportImagePicker
            image={image?.file ?? null}
            previewUrl={previewUrl}
            error={errors.image}
            onSelect={selectReportImage}
            onRemove={removeReportImage}
            inputRef={imageInputRef}
          />
          <div className="report-fields">
            <label className="report-description-field" htmlFor="report-description">
              <span className="form-label">Description <span aria-hidden="true">*</span></span>
              <textarea
                id="report-description"
                className={`form-input report-textarea${errors.description ? ' has-error' : ''}`}
                rows="4"
                placeholder="Describe the garbage and any useful details…"
                value={description}
                onChange={(event) => {
                  setDescription(event.target.value)
                  idempotencyKeyRef.current = null
                  setErrors((current) => ({ ...current, description: '' }))
                  setMessage('')
                  setSubmissionError('')
                }}
                aria-invalid={Boolean(errors.description)}
                aria-describedby={errors.description ? 'report-description-error' : undefined}
              />
              {errors.description && <span className="field-error" id="report-description-error" role="alert">{errors.description}</span>}
            </label>
            <ReportLocationFields
              mode={locationMode}
              onModeChange={(mode) => {
                setLocationMode(mode)
                idempotencyKeyRef.current = null
                setErrors((current) => ({ ...current, location: '' }))
                setMessage('')
                setSubmissionError('')
              }}
              address={address}
              onAddressChange={(value) => {
                setAddress(value)
                idempotencyKeyRef.current = null
                setErrors((current) => ({ ...current, location: '' }))
                setMessage('')
                setSubmissionError('')
              }}
              latitude={latitude}
              onLatitudeChange={(value) => {
                setLatitude(value)
                idempotencyKeyRef.current = null
                setErrors((current) => ({ ...current, location: '' }))
                setMessage('')
                setSubmissionError('')
              }}
              longitude={longitude}
              onLongitudeChange={(value) => {
                setLongitude(value)
                idempotencyKeyRef.current = null
                setErrors((current) => ({ ...current, location: '' }))
                setMessage('')
                setSubmissionError('')
              }}
              errors={errors}
            />
            <div className="report-submit-row">
              <button className="button button--primary report-submit" type="submit" disabled={submitting}>
                {submitting ? <><span className="loading-spinner" /> Submitting report…</> : <>Submit Report <Icon name="arrow" /></>}
              </button>
              <p className="report-demo-note">Saved locally with an AI waste classification</p>
            </div>
            {message && <p className="report-feedback" role="status"><Icon name="check" />{message}</p>}
            {submissionError && <p className="report-form-error" role="alert">{submissionError}</p>}
            {Object.keys(errors).length > 0 && (
              <p className="report-form-error" role="alert">Please fix the highlighted fields before submitting.</p>
            )}
          </div>
        </form>
        <div className="saved-reports" aria-labelledby="saved-reports-heading">
          <div className="saved-reports-heading">
            <h3 id="saved-reports-heading">Recent reports</h3>
            <span>{reportCount} saved</span>
          </div>
          {reportsLoading && <p className="reports-message">Loading saved reports…</p>}
          {reportsError && <p className="report-form-error" role="alert">{reportsError}</p>}
          {!reportsLoading && !reportsError && reports.length === 0 && (
            <p className="reports-message">No reports have been submitted yet.</p>
          )}
          {reports.length > 0 && (
            <ul className="saved-report-list">
              {reports.map((report) => (
                <li className="saved-report" key={report.id}>
                  {report.photo_path && (
                    <img
                      className="saved-report-image"
                      src={`${API_BASE_URL}/${report.photo_path.replace(/^\/+/, '')}`}
                      alt={`Photo for report ${report.id}`}
                      crossOrigin="use-credentials"
                    />
                  )}
                  <div className="saved-report-details">
                    <strong>Report #{report.id}</strong>
                    <p>{report.description}</p>
                    <span>
                      {report.predicted_category
                        ? `AI category: ${report.predicted_category} · ${(report.prediction_confidence * 100).toFixed(1)}% confidence`
                        : 'No classification available'}
                    </span>
                    <small>
                      {report.location || `Coordinates: ${report.latitude}, ${report.longitude}`}
                      {' · '}
                      Complaint #{report.complaint_id ?? 'pending'}
                      {' · '}
                      {report.assigned_department || 'Department pending'}
                      {' · '}
                      Status: {report.complaint_status || report.status}
                    </small>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}

const COMPLAINT_STATUSES = ['New', 'Assigned', 'In Progress', 'Resolved', 'Closed']
const NEXT_COMPLAINT_STATUSES = {
  New: ['Assigned'],
  Assigned: ['In Progress'],
  'In Progress': ['Resolved'],
  Resolved: ['Closed'],
  Closed: [],
}

async function parseApiResponse(response, fallback) {
  const result = await response.json()
  if (!response.ok) {
    const detail = Array.isArray(result.detail)
      ? result.detail.map((issue) => issue.msg).join(' ')
      : result.detail
    throw new Error(detail || `${fallback} (HTTP ${response.status}).`)
  }
  return result
}

function ComplaintPhoto({ path, label }) {
  const [failedPath, setFailedPath] = useState('')
  if (!path || failedPath === path) {
    return <p className="complaint-photo-unavailable">{label}: photo unavailable</p>
  }
  return (
    <figure className="complaint-photo">
      <figcaption>{label}</figcaption>
      <img
        src={`${API_BASE_URL}/${path.replace(/^\/+/, '')}`}
        alt={label}
        crossOrigin="use-credentials"
        onError={() => setFailedPath(path)}
      />
    </figure>
  )
}

function ComplaintPhotoGallery({ complaint, showAfter = true }) {
  return (
    <div className="complaint-photo-gallery">
      <ComplaintPhoto path={complaint.before_cleaning_photo_path} label="Before Cleaning" />
      {showAfter && (
        <ComplaintPhoto path={complaint.after_cleaning_photo_path} label="After Cleaning" />
      )}
    </div>
  )
}

function ComplaintDashboard({ authorityMode = false }) {
  const [complaints, setComplaints] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [selectedComplaint, setSelectedComplaint] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [departmentFilter, setDepartmentFilter] = useState('')
  const [locationFilter, setLocationFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [createdAfter, setCreatedAfter] = useState('')
  const [createdBefore, setCreatedBefore] = useState('')
  const [refreshVersion, setRefreshVersion] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [updateMessage, setUpdateMessage] = useState('')
  const [updateError, setUpdateError] = useState('')
  const [nextStatus, setNextStatus] = useState('')
  const [staffNote, setStaffNote] = useState('')
  const [afterCleaningPhoto, setAfterCleaningPhoto] = useState(null)
  const [updating, setUpdating] = useState(false)
  const [departmentName, setDepartmentName] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    const params = new URLSearchParams()
    if (statusFilter) params.set('status', statusFilter)
    if (departmentFilter.trim()) params.set('department', departmentFilter.trim())
    if (locationFilter.trim()) params.set('location', locationFilter.trim())
    if (categoryFilter) params.set('category', categoryFilter)
    if (createdAfter) params.set('created_after', createdAfter)
    if (createdBefore) params.set('created_before', createdBefore)

    async function loadComplaints() {
      setLoading(true)
      try {
        const queryString = params.toString()
        const query = queryString ? `?${queryString}` : ''
        const response = await fetch(`${API_BASE_URL}/api/complaints${query}`, {
          credentials: 'include',
          signal: controller.signal,
        })
        const result = await parseApiResponse(response, 'Complaints could not be loaded')
        setComplaints(result)
        setError('')
      } catch (loadError) {
        if (loadError.name !== 'AbortError') {
          setError(loadError instanceof TypeError
            ? `Could not connect to the local API at ${API_BASE_URL}.`
            : loadError.message || 'Complaints could not be loaded.')
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }

    loadComplaints()
    return () => controller.abort()
  }, [statusFilter, departmentFilter, locationFilter, categoryFilter, createdAfter, createdBefore, refreshVersion])

  useEffect(() => {
    if (!selectedId) {
      return undefined
    }
    const controller = new AbortController()
    async function loadDetails() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/complaints/${selectedId}`, {
          credentials: 'include',
          signal: controller.signal,
        })
        setSelectedComplaint(await parseApiResponse(response, 'Complaint details could not be loaded'))
        setUpdateError('')
      } catch (loadError) {
        if (loadError.name !== 'AbortError') {
          setUpdateError(loadError instanceof TypeError
            ? `Could not connect to the local API at ${API_BASE_URL}.`
            : loadError.message || 'Complaint details could not be loaded.')
        }
      }
    }
    loadDetails()
    return () => controller.abort()
  }, [selectedId, refreshVersion])

  async function updateStatus(event) {
    event.preventDefault()
    if (!selectedComplaint || !nextStatus || updating) return
    setUpdating(true)
    setUpdateError('')
    setUpdateMessage('')
    try {
      const resolving = nextStatus === 'Resolved'
      const body = resolving
        ? (() => {
            const formData = new FormData()
            formData.append('after_cleaning_photo', afterCleaningPhoto)
            if (staffNote.trim()) formData.append('staff_note', staffNote.trim())
            return formData
          })()
        : JSON.stringify({
            status: nextStatus,
            staff_note: staffNote.trim() || null,
          })
      const response = await fetch(
        `${API_BASE_URL}/api/complaints/${selectedComplaint.id}/${resolving ? 'resolve' : 'status'}`,
        {
          method: 'PUT',
          credentials: 'include',
          ...(resolving ? {} : { headers: { 'Content-Type': 'application/json' } }),
          body,
        },
      )
      const result = await parseApiResponse(response, 'Complaint status could not be updated')
      setSelectedComplaint(result)
      setNextStatus('')
      setStaffNote('')
      setAfterCleaningPhoto(null)
      setDepartmentName(result.assigned_department)
      setUpdateMessage(`Complaint #${result.id} is now ${result.status}.`)
      setRefreshVersion((version) => version + 1)
    } catch (updateFailure) {
      setUpdateError(updateFailure instanceof TypeError
        ? `Could not connect to the local API at ${API_BASE_URL}.`
        : updateFailure.message || 'Complaint status could not be updated.')
    } finally {
      setUpdating(false)
    }
  }

  async function assignDepartment(event) {
    event.preventDefault()
    if (!selectedComplaint || !departmentName.trim() || updating) return
    setUpdating(true)
    setUpdateError('')
    setUpdateMessage('')
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/complaints/${selectedComplaint.id}/assignment`,
        {
          method: 'PUT',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ assigned_department: departmentName.trim() }),
        },
      )
      const result = await parseApiResponse(response, 'Complaint assignment could not be updated')
      setSelectedComplaint(result)
      setDepartmentName(result.assigned_department)
      setUpdateMessage(`Complaint #${result.id} assigned to ${result.assigned_department}.`)
      setRefreshVersion((version) => version + 1)
    } catch (assignmentError) {
      setUpdateError(assignmentError instanceof TypeError
        ? `Could not connect to the local API at ${API_BASE_URL}.`
        : assignmentError.message || 'Complaint assignment could not be updated.')
    } finally {
      setUpdating(false)
    }
  }

  function renderComplaintCard(complaint) {
    return (
      <button
        type="button"
        className={`complaint-list-item${selectedId === complaint.id ? ' is-selected' : ''}`}
        key={complaint.id}
        onClick={() => {
          setSelectedId(complaint.id)
          setSelectedComplaint(null)
          setDepartmentName(complaint.assigned_department)
          setAfterCleaningPhoto(null)
          setUpdateMessage('')
          setUpdateError('')
        }}
      >
        <strong>Complaint #{complaint.id}</strong>
        <span>
          {complaint.waste_category}
          {complaint.prediction_confidence != null
            ? ` · ${(complaint.prediction_confidence * 100).toFixed(1)}% confidence`
            : ''}
          {' · '}
          {complaint.status}
        </span>
        <small>{complaint.assigned_department} · {complaint.location}</small>
        {complaint.status === 'Resolved' && (
          <ComplaintPhotoGallery complaint={complaint} />
        )}
      </button>
    )
  }

  return (
    <section className="complaint-section" id="complaints">
      <div className="container complaint-container">
        <div className="classifier-heading">
          <span className="eyebrow">{authorityMode ? 'Municipal operations' : 'Your activity'}</span>
          <h2>{authorityMode ? 'Authority dashboard' : 'Your complaints'}</h2>
          <p>{authorityMode
            ? 'Review all reports, assign departments, and record cleanup progress.'
            : 'Follow the progress of your reports and review their status history.'}</p>
        </div>
        {authorityMode && (
          <div className="authority-summary" aria-label="Complaint summary statistics">
            {COMPLAINT_STATUSES.map((status) => (
              <article key={status}>
                <strong>{complaints.filter((complaint) => complaint.status === status).length}</strong>
                <span>{status}</span>
              </article>
            ))}
          </div>
        )}
        <div className="complaint-filters" aria-label="Filter complaints">
          <label>
            <span>Status</span>
            <select className="form-input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">All statuses</option>
              {COMPLAINT_STATUSES.map((status) => <option key={status}>{status}</option>)}
            </select>
          </label>
          {authorityMode && (
            <label>
              <span>Department</span>
              <input className="form-input" value={departmentFilter} onChange={(event) => setDepartmentFilter(event.target.value)} placeholder="Filter department" />
            </label>
          )}
          <label>
            <span>Location</span>
            <input className="form-input" value={locationFilter} onChange={(event) => setLocationFilter(event.target.value)} placeholder="Filter location" />
          </label>
          <label>
            <span>Category</span>
            <select className="form-input" value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
              <option value="">All categories</option>
              <option>Wet Waste</option>
              <option>Dry Waste</option>
            </select>
          </label>
          <label>
            <span>From date</span>
            <input className="form-input" type="date" value={createdAfter} onChange={(event) => setCreatedAfter(event.target.value)} />
          </label>
          <label>
            <span>To date</span>
            <input className="form-input" type="date" value={createdBefore} onChange={(event) => setCreatedBefore(event.target.value)} />
          </label>
        </div>
        {error && <p className="report-form-error" role="alert">{error}</p>}
        <div className="complaint-dashboard">
          <div className="complaint-list-panel" aria-label="Complaints">
            {loading && <p className="reports-message">Loading complaints…</p>}
            {!loading && !error && complaints.length === 0 && (
              <p className="reports-message">No complaints match these filters.</p>
            )}
            {!loading && !error && complaints.length > 0 && (
              statusFilter ? (
                <section className="complaint-list-group">
                  <h4>{statusFilter} complaints</h4>
                  {complaints.map(renderComplaintCard)}
                </section>
              ) : (
                <>
                  <section className="complaint-list-group">
                    <h4>Resolved complaints</h4>
                    {complaints
                      .filter((complaint) => complaint.status === 'Resolved')
                      .map(renderComplaintCard)}
                    {!complaints.some((complaint) => complaint.status === 'Resolved') && (
                      <p className="reports-message">No resolved complaints yet.</p>
                    )}
                  </section>
                  <section className="complaint-list-group">
                    <h4>Other complaints</h4>
                    {complaints
                      .filter((complaint) => complaint.status !== 'Resolved')
                      .map(renderComplaintCard)}
                  </section>
                </>
              )
            )}
          </div>
          <div className="complaint-detail-panel">
            {!selectedId && <p className="reports-message">Select a complaint to inspect its details and status history.</p>}
            {selectedId && !selectedComplaint && !updateError && (
              <p className="reports-message">Loading complaint details…</p>
            )}
            {selectedComplaint && (
              <>
                <div className="complaint-detail-heading">
                  <div>
                    <span className="eyebrow">Complaint #{selectedComplaint.id}</span>
                    <h3>{selectedComplaint.status}</h3>
                  </div>
                  <span className="complaint-category">{selectedComplaint.waste_category}</span>
                </div>
                <dl className="complaint-facts">
                  <div><dt>Linked report</dt><dd>#{selectedComplaint.report_id}</dd></div>
                  <div><dt>Assigned department</dt><dd>{selectedComplaint.assigned_department}</dd></div>
                  <div>
                    <dt>AI classification</dt>
                    <dd>
                      {selectedComplaint.waste_category}
                      {selectedComplaint.prediction_confidence != null
                        ? ` · ${(selectedComplaint.prediction_confidence * 100).toFixed(1)}% confidence`
                        : ' · confidence unavailable'}
                      {selectedComplaint.model_version ? ` · ${selectedComplaint.model_version}` : ''}
                    </dd>
                  </div>
                  <div><dt>Location</dt><dd>{selectedComplaint.location}</dd></div>
                  <div><dt>Description</dt><dd>{selectedComplaint.description}</dd></div>
                </dl>
                <ComplaintPhotoGallery complaint={selectedComplaint} />
                <h4>Status history</h4>
                <ol className="complaint-history">
                  {selectedComplaint.status_history.map((entry, index) => (
                    <li key={`${entry.changed_at}-${index}`}>
                      <strong>
                        {entry.event_type === 'assignment'
                          ? 'Department assignment'
                          : `${entry.previous_status || 'Created'} → ${entry.new_status}`}
                      </strong>
                      <time>{new Date(entry.changed_at).toLocaleString()}</time>
                      {entry.staff_note && <p>{entry.staff_note}</p>}
                      {entry.changed_by && <small>Updated by {entry.changed_by}</small>}
                    </li>
                  ))}
                </ol>
                {authorityMode && (
                  <form className="complaint-update-form" onSubmit={assignDepartment}>
                    <label>
                      <span>Assigned department or team</span>
                      <input
                        className="form-input"
                        maxLength={200}
                        value={departmentName}
                        onChange={(event) => setDepartmentName(event.target.value)}
                        required
                      />
                    </label>
                    <button className="button button--light" type="submit" disabled={updating || !departmentName.trim()}>
                      Save assignment
                    </button>
                  </form>
                )}
                {authorityMode && NEXT_COMPLAINT_STATUSES[selectedComplaint.status].length > 0 && (
                  <form className="complaint-update-form" onSubmit={updateStatus}>
                    <label>
                      <span>Move status to</span>
                      <select className="form-input" value={nextStatus} onChange={(event) => setNextStatus(event.target.value)} required>
                        <option value="">Choose next status</option>
                        {NEXT_COMPLAINT_STATUSES[selectedComplaint.status].map((status) => (
                          <option key={status}>{status}</option>
                        ))}
                      </select>
                    </label>
                    {nextStatus === 'Resolved' && (
                      <label>
                        <span>After Cleaning Photo (required)</span>
                        <input
                          key={`${selectedComplaint.id}-${selectedComplaint.status}`}
                          className="form-input"
                          type="file"
                          accept="image/jpeg,image/png,image/webp"
                          required
                          onChange={(event) => {
                            const file = event.target.files?.[0] ?? null
                            if (!file) {
                              setAfterCleaningPhoto(null)
                              setUpdateError('')
                              return
                            }
                            if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
                              setAfterCleaningPhoto(null)
                              setUpdateError('Choose a JPEG, PNG, or WebP after-cleaning photo.')
                              event.target.value = ''
                              return
                            }
                            if (file.size > MAX_IMAGE_SIZE) {
                              setAfterCleaningPhoto(null)
                              setUpdateError('The after-cleaning photo must be 10 MB or smaller.')
                              event.target.value = ''
                              return
                            }
                            setAfterCleaningPhoto(file)
                            setUpdateError('')
                          }}
                        />
                        {afterCleaningPhoto && (
                          <small className="complaint-photo-filename">
                            Selected: {afterCleaningPhoto.name}
                          </small>
                        )}
                      </label>
                    )}
                    <label>
                      <span>Optional note</span>
                      <textarea className="form-input" maxLength={1000} rows="2" value={staffNote} onChange={(event) => setStaffNote(event.target.value)} />
                    </label>
                    <button
                      className="button button--primary"
                      type="submit"
                      disabled={updating || !nextStatus || (nextStatus === 'Resolved' && !afterCleaningPhoto)}
                    >
                      {updating ? 'Saving…' : 'Update status'}
                    </button>
                  </form>
                )}
              </>
            )}
            {updateMessage && <p className="report-feedback" role="status">{updateMessage}</p>}
            {updateError && <p className="report-form-error" role="alert">{updateError}</p>}
          </div>
        </div>
      </div>
    </section>
  )
}

const features = [
  {
    icon: 'recycle',
    title: 'Sort it smarter',
    description: 'Get a little help figuring out what goes where with AI-powered waste classification.',
    tone: 'mint',
  },
  {
    icon: 'location',
    title: 'Report what you see',
    description: 'Spot an overflowing bin or littered street? Share the location so it can be addressed.',
    tone: 'peach',
  },
  {
    icon: 'shield',
    title: 'See action happen',
    description: 'Follow reported issues as local sanitation teams work toward a cleaner neighborhood.',
    tone: 'lavender',
  },
]

function FeatureCard({ feature }) {
  return (
    <article className="feature-card">
      <span className={`feature-icon feature-icon--${feature.tone}`}><Icon name={feature.icon} /></span>
      <h3>{feature.title}</h3>
      <p>{feature.description}</p>
    </article>
  )
}

function Services() {
  return (
    <section className="services-section" id="services">
      <div className="container">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Your next step</span>
            <h2>Good things start<br />with <span>one small action.</span></h2>
          </div>
          <p>Whether you’re sorting at home or out in your community, it’s easy to get involved.</p>
        </div>
        <div className="action-grid">
          <ActionCard
            icon="sparkle"
            label="AI-powered"
            title="Not sure where it goes?"
            description="Snap a photo and let our AI help classify your waste as wet or dry."
            button="Classify my waste"
            href="#waste-classifier"
            variant="ai"
          />
          <ActionCard
            icon="camera"
            label="Community care"
            title="See a mess? Say something."
            description="Help keep your neighborhood clean. Report garbage with a photo and location."
            button="Report an issue"
            href="/user/login"
            variant="report"
          />
        </div>
      </div>
    </section>
  )
}

function HowItWorks() {
  return (
    <section className="features-section container" id="how-it-works">
      <div className="section-heading section-heading--center">
        <span className="eyebrow">Better, together</span>
        <h2>A simple way to make<br />a <span>real difference.</span></h2>
        <p>Small steps add up. Here’s how EcoSort helps turn everyday actions into lasting impact.</p>
      </div>
      <div className="feature-grid">
        {features.map((feature) => <FeatureCard key={feature.title} feature={feature} />)}
      </div>
      <div className="impact-banner">
        <div className="impact-icon"><Icon name="chart" /></div>
        <div>
          <h3>Every action adds up</h3>
          <p>Be part of a community making cleaner, greener neighborhoods possible.</p>
        </div>
        <a className="text-link" href="#services">Get involved <Icon name="arrow" /></a>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-content">
        <div>
          <Brand footer />
          <p className="footer-tagline">A little care goes a long way.</p>
        </div>
        <p className="footer-note"><Icon name="leaf" /> Made for cleaner communities <span>© 2026 EcoSort</span></p>
      </div>
    </footer>
  )
}

function AuthPage({ role, registration = false, initialError = '' }) {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const isAuthority = role === 'authority'

  async function submit(event) {
    event.preventDefault()
    if (loading) return
    setError('')
    if (registration && password !== confirmation) {
      setError('The passwords do not match.')
      return
    }
    setLoading(true)
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/auth/${registration ? 'register' : 'login'}`,
        {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(registration
            ? { full_name: fullName, email, password }
            : { email, password, role }),
        },
      )
      const result = await parseApiResponse(response, registration ? 'Registration failed' : 'Sign-in failed')
      window.location.href = result.role === 'authority' ? '/authority/dashboard' : '/user/dashboard'
    } catch (requestError) {
      setError(requestError instanceof TypeError
        ? `Could not connect to the local API at ${API_BASE_URL}.`
        : requestError.message || 'Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Navbar />
      <main className="auth-page">
        <div className="auth-card">
          <span className="eyebrow">{isAuthority ? 'Municipal operations' : 'Community account'}</span>
          <h1>{registration ? 'Create your citizen account' : `${isAuthority ? 'Municipal authority' : 'User'} login`}</h1>
          <p>
            {registration
              ? 'Register to submit reports and follow your neighborhood complaints.'
              : isAuthority
                ? 'Sign in with an administrator-provisioned authority account.'
                : 'Sign in to report waste and track your submitted complaints.'}
          </p>
          {initialError && <p className="report-form-error" role="alert">{initialError}</p>}
          <form className="auth-form" onSubmit={submit}>
            {registration && (
              <label>
                <span>Full name</span>
                <input className="form-input" autoComplete="name" maxLength={150} required value={fullName} onChange={(event) => setFullName(event.target.value)} />
              </label>
            )}
            <label>
              <span>Email</span>
              <input className="form-input" type="email" autoComplete="username" maxLength={320} required value={email} onChange={(event) => setEmail(event.target.value)} />
            </label>
            <label>
              <span>Password</span>
              <input className="form-input" type="password" autoComplete={registration ? 'new-password' : 'current-password'} minLength={registration ? 12 : undefined} maxLength={128} required value={password} onChange={(event) => setPassword(event.target.value)} />
            </label>
            {registration && (
              <>
                <small className="auth-password-note">Use at least 12 characters.</small>
                <label>
                  <span>Confirm password</span>
                  <input className="form-input" type="password" autoComplete="new-password" maxLength={128} required value={confirmation} onChange={(event) => setConfirmation(event.target.value)} />
                </label>
              </>
            )}
            <button className="button button--primary auth-submit" type="submit" disabled={loading}>
              {loading ? 'Please wait…' : registration ? 'Create account' : 'Sign in'}
            </button>
            {error && <p className="report-form-error" role="alert">{error}</p>}
          </form>
          <div className="auth-links">
            {!isAuthority && (registration
              ? <a href="/user/login">Already registered? Sign in</a>
              : <a href="/user/register">New to EcoSort? Create a user account</a>)}
            <a href={isAuthority ? '/user/login' : '/authority/login'}>
              {isAuthority ? 'Go to User Login' : 'Municipal Authority Login'}
            </a>
          </div>
          {isAuthority && <p className="authority-provision-note">Municipal accounts are not created through public registration.</p>}
        </div>
      </main>
      <Footer />
    </>
  )
}

function ProfileCard({ user, onProfileUpdate }) {
  const [fullName, setFullName] = useState(user.full_name)
  const [email, setEmail] = useState(user.email)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function saveProfile(event) {
    event.preventDefault()
    if (loading) return
    setLoading(true)
    setMessage('')
    setError('')
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: fullName, email }),
      })
      const updatedUser = await parseApiResponse(response, 'Profile could not be updated')
      onProfileUpdate(updatedUser)
      setMessage('Profile updated.')
    } catch (requestError) {
      setError(requestError instanceof TypeError
        ? `Could not connect to the local API at ${API_BASE_URL}.`
        : requestError.message || 'Profile could not be updated.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form className="profile-card" onSubmit={saveProfile}>
      <div>
        <span className="eyebrow">Your profile</span>
        <p>Update your name and email associated with this account.</p>
      </div>
      <label><span>Full name</span><input className="form-input" maxLength={150} required value={fullName} onChange={(event) => setFullName(event.target.value)} /></label>
      <label><span>Email</span><input className="form-input" type="email" maxLength={320} required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
      <button className="button button--light" type="submit" disabled={loading}>{loading ? 'Saving…' : 'Save profile'}</button>
      {message && <p className="report-feedback" role="status">{message}</p>}
      {error && <p className="report-form-error" role="alert">{error}</p>}
    </form>
  )
}

function DashboardPage({ user, authorityMode, onProfileUpdate }) {
  return (
    <>
      <Navbar user={user} />
      <main className="dashboard-page">
        <section className="dashboard-welcome container">
          <span className="eyebrow">{authorityMode ? 'Municipal authority workspace' : 'Citizen workspace'}</span>
          <h1>Welcome, {user.full_name}</h1>
          <p>{authorityMode
            ? 'Coordinate cleanup requests and keep residents informed.'
            : 'Submit a waste report or check the latest progress on your complaints.'}</p>
          <ProfileCard user={user} onProfileUpdate={onProfileUpdate} />
        </section>
        {authorityMode ? (
          <ComplaintDashboard authorityMode />
        ) : (
          <>
            <GarbageReportForm />
            <ComplaintDashboard />
          </>
        )}
      </main>
      <Footer />
    </>
  )
}

function App() {
  const [user, setUser] = useState(null)
  const [sessionLoading, setSessionLoading] = useState(true)
  const [sessionError, setSessionError] = useState('')
  const path = window.location.pathname.replace(/\/+$/, '') || '/'
  const isAuthorityPath = path.startsWith('/authority')
  const isDashboard = path.endsWith('/dashboard')
  const isRegistration = path === '/user/register'
  const isAuthPath = path !== '/' && !isDashboard
  const expectedRole = isAuthorityPath ? 'authority' : 'citizen'

  useEffect(() => {
    const controller = new AbortController()
    async function loadSession() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
          credentials: 'include',
          signal: controller.signal,
        })
        if (response.ok) setUser(await response.json())
        else setUser(null)
      } catch (requestError) {
        if (requestError.name !== 'AbortError') {
          setUser(null)
          setSessionError(`Could not connect to the local API at ${API_BASE_URL}.`)
        }
      } finally {
        if (!controller.signal.aborted) setSessionLoading(false)
      }
    }
    loadSession()
    return () => controller.abort()
  }, [])

  if (sessionLoading && (isDashboard || isAuthPath)) {
    return <main className="auth-page"><p className="reports-message">Checking your session…</p></main>
  }
  if (isDashboard && user && user.role !== expectedRole) {
    return (
      <>
        <Navbar user={user} />
        <main className="auth-page">
          <div className="auth-card">
            <h1>This dashboard is not available to your account</h1>
            <p>Sign in with the correct account type to continue.</p>
            <a className="button button--primary" href={user.role === 'authority' ? '/authority/dashboard' : '/user/dashboard'}>Go to your dashboard</a>
          </div>
        </main>
      </>
    )
  }
  if (isDashboard && !user) {
    return <AuthPage role={expectedRole} initialError={sessionError} />
  }
  if (isAuthPath) {
    return (
      <>
        {sessionError && <p className="session-error" role="alert">{sessionError}</p>}
        <AuthPage role={expectedRole} registration={isRegistration} />
      </>
    )
  }
  if (isDashboard && user) {
    return <DashboardPage user={user} authorityMode={expectedRole === 'authority'} onProfileUpdate={setUser} />
  }

  return (
    <>
      <Navbar user={user} />
      <main>
        <Hero />
        <RoleSelection />
        <Services />
        <WasteClassifier />
        <HowItWorks />
      </main>
      <Footer />
    </>
  )
}

export default App
