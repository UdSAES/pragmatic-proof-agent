// Implementation of the photo-API used as example on RESTdesc.org

'use strict'

const crypto = require('crypto')

const _ = require('lodash')
const fs = require('fs-extra')
const bunyan = require('bunyan')
const express = require('express')
const { processenv } = require('processenv')
const fileUpload = require('express-fileupload')

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

// Read configuration
async function readConfig () {
  const config = {
    language: processenv('IMG_API_LANG', 'en'),
    tmpDirectory: processenv('IMG_API_TMP', '/tmp'),
    listenPort: processenv('IMG_API_PORT', 3000),
  }

  log.debug({ config: config }, 'Instance configuration loaded')

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

// Describe hypermedia API using RESTdesc
async function n3addImage (req, res) {
  await respondWithNotImplemented(req, res)
}

async function n3getImage (req, res) {
  await respondWithNotImplemented(req, res)
}

async function n3getThumbnail (req, res) {
  await respondWithNotImplemented(req, res)
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
  const fileExtension = _.last(_.split(fileName, '.'))
  const buffer = req.files.image.data
  const hash = crypto
    .createHash('md5')
    .update(buffer)
    .digest('hex')

  // Store file on disk
  const filePath = `${baseDir}/${hash}.${fileExtension}`
  const filePathExists = await fs.pathExists(filePath)

  if (!filePathExists) {
    await fs.ensureDir(baseDir)
    await fs.writeFile(filePath, buffer)
  }

  log.debug(`Added image \`${fileName}\` to API-instance as \`${hash}.${fileExtension}\``)

  // Acknowlegde successfull addition
  const imagePath = _.replace(cfg.paths.specificImage, ':imageId', hash)
  res.status(201).location(`${origin}${imagePath}`).json()
}

async function getImage (req, res) {
  await respondWithNotImplemented(req, res)
}

async function getThumbnail (req, res) {
  await respondWithNotImplemented(req, res)
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
