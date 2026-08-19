import { createContext, useContext, type ReactNode } from 'react'

/**
 * Nesting depth of the field currently being rendered.
 *
 * The form is generated from a schema, so nothing in the markup says how deeply
 * a field sits. Depth cannot be recovered from CSS either, because an array
 * between two objects breaks any fixed chain of child selectors, and it cannot
 * be parsed out of the generated element id because RSM property names contain
 * underscores themselves. Tracking it in context is the one reading that stays
 * correct for every shape the schema can take.
 */
const FieldDepthContext = createContext(0)

export function useFieldDepth(): number {
  return useContext(FieldDepthContext)
}

interface FieldDepthProviderProps {
  depth: number
  children: ReactNode
}

export function FieldDepthProvider({ depth, children }: FieldDepthProviderProps) {
  return <FieldDepthContext.Provider value={depth}>{children}</FieldDepthContext.Provider>
}
