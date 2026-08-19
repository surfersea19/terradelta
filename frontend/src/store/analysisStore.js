import { create } from 'zustand'

export const useAnalysisStore = create((set) => ({
  // Form state
  bbox:          null,  // [lon_min, lat_min, lon_max, lat_max]
  dates:         ['', ''], // Array of YYYY-MM-DD
  locationName:  '',

  // Job state
  jobId:         null,
  jobStatus:     null,  // queued | processing | complete | failed
  jobProgress:   0,
  jobMessage:    '',

  // Result
  result:        null,
  activeLayer:   'after',   // before | after | change
  activeStep:    1,         // index of the current change step (1 to images.length - 1)

  // Actions
  setBbox:        (bbox)    => set({ bbox }),
  setDates:       (dates)   => set({ dates }),
  setLocationName:(name)    => set({ locationName: name }),
  setJobId:       (jobId)   => set({ jobId }),
  setJobStatus:   (s, p, m) => set({ jobStatus: s, jobProgress: p, jobMessage: m }),
  setResult:      (result)  => set({ result, activeStep: 1, activeLayer: 'after' }),
  setActiveLayer: (layer)   => set({ activeLayer: layer }),
  setActiveStep:  (step)    => set({ activeStep: step }),

  reset: () => set({
    jobId: null, jobStatus: null, jobProgress: 0,
    jobMessage: '', result: null, activeLayer: 'after', activeStep: 1
  }),
}))

export const useMonitoringStore = create((set) => ({
  bbox:      null,
  dates:     ['', ''],
  jobId:     null,
  status:    null,
  progress:  0,
  result:    null,
  activeDate: 0,

  setBbox:       (bbox)  => set({ bbox }),
  setDates:      (dates) => set({ dates }),
  setJobId:      (id)    => set({ jobId: id }),
  setStatus:     (s, p)  => set({ status: s, progress: p }),
  setResult:     (r)     => set({ result: r }),
  setActiveDate: (i)     => set({ activeDate: i }),
  reset: () => set({ jobId: null, status: null, progress: 0, result: null }),
}))
