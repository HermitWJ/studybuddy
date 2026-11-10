import request from './request'

export const getHealth = () => request.get('/health/')

export const getTasks = () => request.get('/tasks/')

export const createTask = (data) => request.post('/tasks/', data)

export const updateTask = (id, data) => request.patch(`/tasks/${id}/`, data)

export const deleteTask = (id) => request.delete(`/tasks/${id}/`)
