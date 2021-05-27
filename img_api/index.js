// Implementation of the photo-API used as example on RESTdesc.org

'use strict'

const crypto = require('crypto')

const _ = require('lodash')
const fs = require('fs-extra')
const bunyan = require('bunyan')
const express = require('express')
const { promisify } = require('util')
const { processenv } = require('processenv')
const fileUpload = require('express-fileupload')
const execFile = promisify(require('child_process').execFile)

// Instantiate logger
const log = bunyan.createLogger({
  name: 'img_api', // TODO make configurable?
  stream: process.stdout,
  level: processenv('IMG_API_LOGLEVEL', bunyan.INFO),
  serializers: {
    err: bunyan.stdSerializers.err,
    req: bunyan.stdSerializers.req,
    res: function (res) {
      if (!res || !res.statusCode) {
        return res
      }
      return {
        statusCode: res.statusCode,
        headers: res._headers
      }
    }
  }
})

const images = {}

// Read configuration
async function readConfig () {
  const config = {
    language: processenv('IMG_API_LANG', 'en'),
    tmpDirectory: processenv('IMG_API_TMP', '/tmp'),
    listenPort: processenv('IMG_API_PORT', 3000)
  }

  // Construct resource paths
  const lang = config.language
  const resourceNames = {
    images: {
      en: 'images',
      de: 'bilder',
      fr: 'photos'
    },
    thumbnail: {
      en: 'thumbnail',
      de: 'miniaturbild',
      fr: 'miniature'
    }
  }

  const collectionOfImages = `/${resourceNames.images[lang]}`
  const specificImage = `${collectionOfImages}/:imageId`
  const thumbnail = `${specificImage}/${resourceNames.thumbnail[lang]}`

  config.paths = {
    collectionOfImages: collectionOfImages,
    specificImage: specificImage,
    thumbnail: thumbnail
  }

  return config
}

// Perform actual work
async function resizeImage (original, resized, size) {
  await execFile('/usr/bin/convert', [original, '-resize', size, resized])
  log.debug(`Resized file to ${size} px (keeping the aspect ratio)`)
}

// Describe hypermedia API using RESTdesc
async function n3addImage (req, res) {
  const filePath = './restdesc/add_image.n3'
  const RESTdesc = await fs.readFile(filePath, { encoding: 'utf-8' })

  res.set('Allow', 'POST,HEAD,OPTIONS')
  res.set('Content-Type', 'text/n3')
  res.status(200).send(RESTdesc)
}

async function n3getImage (req, res) {
  const filePath = './restdesc/get_image.n3'
  const RESTdesc = await fs.readFile(filePath, { encoding: 'utf-8' })

  res.set('Allow', 'GET,HEAD,OPTIONS')
  res.set('Content-Type', 'text/n3')
  res.status(200).send(RESTdesc)
}

async function n3getThumbnail (req, res) {
  const filePath = './restdesc/get_thumbnail.n3'
  const RESTdesc = await fs.readFile(filePath, { encoding: 'utf-8' })

  res.set('Allow', 'GET,HEAD,OPTIONS')
  res.set('Content-Type', 'text/n3')
  res.status(200).send(RESTdesc)
}

// Define request handlers
async function browseAPI (req, res) {
  await respondWithNotImplemented(req, res)
}

async function addImage (req, res) {
  const host = _.get(req, ['headers', 'host'])
  const protocol = _.get(req, ['protocol'])
  const origin = `${protocol}://${host}`

  const cfg = await readConfig()
  const baseDir = `${cfg.tmpDirectory}/images`

  // Create new identifier for image
  const fileName = req.files.image.name
  const buffer = req.files.image.data
  const hash = crypto
    .createHash('md5')
    .update(buffer)
    .digest('hex')

  // Store file on disk
  const filePath = `${baseDir}/${fileName}`
  const filePathExists = await fs.pathExists(filePath)

  if (!filePathExists) {
    await fs.ensureDir(baseDir)
    await fs.writeFile(filePath, buffer)
  }

  // Update knowledge about resource state
  images[hash] = {
    fileName: fileName,
    filePath: filePath
  }
  log.debug(`Added image \`${fileName}\` to API-instance as \`/images/${hash}\``)
  log.trace({ images: images })

  // Acknowlegde successfull addition
  const imagePath = _.replace(cfg.paths.specificImage, ':imageId', hash)
  res
    .status(201)
    .location(`${origin}${imagePath}`)
    .json()
}

async function getImage (req, res) {
  const hash = _.last(_.split(req.path, '/'))
  const file = images[hash].filePath

  res.sendFile(file)
}

async function getThumbnail (req, res) {
  const hash = _.nth(_.split(req.path, '/'), -2)
  const filePath = images[hash].filePath
  const fileName = images[hash].fileName

  const cfg = await readConfig()
  const baseDir = `${cfg.tmpDirectory}/thumbs`

  const thumbnail = `${baseDir}/${fileName}`

  await fs.ensureDir(baseDir)
  await resizeImage(filePath, thumbnail, 80)

  res.sendFile(thumbnail)
}

// Properly respond in case of errors
async function sendProblemDetail (res, config) {
  // `config` is a dictionary containing the fields from RFC 7807
  // field `status` is required; `detail`, `type`, `title`, `instance` are optional
  res.set('Content-Type', 'application/problem+json')
  const statusCode = config.status
  res.status(statusCode).json(config)
}

async function respondWithNotImplemented (req, res) {
  await sendProblemDetail(res, {
    title: 'Not Implemented',
    status: 501,
    detail:
      'The request was understood, but the underlying implementation is not available yet.'
  })
  log.info(`\`${req.method} ${req.path}\` -> \`501 Not Implemented\``)
}

async function respondWithNotFound (req, res) {
  await sendProblemDetail(res, {
    title: 'Not Found',
    status: 404,
    detail: 'The requested resource was not found on this server'
  })
  log.info(`\`${req.method} ${req.path}\` -> \`404 Not Found\``)
}

// Initialize server
async function init () {
  const cfg = await readConfig()
  log.debug({ config: cfg }, 'Instance configuration loaded')

  // Instantiate express-application and set up middleware-stack
  const app = express()
  app.use(fileUpload())

  // Define routing
  app.get('/', browseAPI)

  app.options(cfg.paths.collectionOfImages, n3addImage)
  app.post(cfg.paths.collectionOfImages, addImage)

  app.options(cfg.paths.specificImage, n3getImage)
  app.get(cfg.paths.specificImage, getImage)

  app.options(cfg.paths.thumbnail, n3getThumbnail)
  app.get(cfg.paths.thumbnail, getThumbnail)

  // Send 404 as reaction to all other requests
  app.use((req, res, next) => respondWithNotFound(req, res, next))

  // Start listening to incoming requests
  app.listen(cfg.listenPort, function () {
    log.info(`Listening on port ${cfg.listenPort}`)
  })
}

// Run when executed as module
if (require.main === module) {
  init()
}
